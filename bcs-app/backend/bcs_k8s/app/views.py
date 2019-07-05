# -*- coding: utf-8 -*-
#
# Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
# Copyright (C) 2017-2019 THL A29 Limited, a Tencent company. All rights reserved.
# Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://opensource.org/licenses/MIT
#
# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
# an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.
#
import os
import json
import base64
import urllib
import logging

from operator import itemgetter
from itertools import groupby
import tempfile
from django.utils import timezone

import yaml
from rest_framework import viewsets
from rest_framework.serializers import Serializer
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import APIException
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.db import IntegrityError
from jinja2 import Template
from django.template.loader import render_to_string

from .models import App
from .serializers import (
    AppSLZ, AppUpgradeSLZ, AppRollbackSLZ, NamespaceSLZ, AppDetailSLZ,
    AppUpgradeVersionsSLZ, AppRollbackSelectionsSLZ, AppReleaseDiffSLZ,
    AppReleasePreviewSLZ, AppCreatePreviewSLZ, AppRollbackPreviewSLZ, AppPreviewSLZ,
    ClusterImportSLZ, ClusterKubeConfigSLZ, SyncDict2YamlToolSLZ, SyncYaml2DictToolSLZ,
    ClusterHelmInitSLZ, AppCreatePreviewDiffWithClusterSLZ, AppStateSLZ, AppUpgradeByAPISLZ
)
from backend.bcs_k8s.helm.serializers import ChartVersionSLZ
from backend.bcs_k8s.helm.models.chart import ChartVersion
from backend.bcs_k8s.helm.models.repo import Repository
from backend.bcs_k8s.diff import parser
from backend.bcs_k8s.permissions import check_cluster_perm
from backend.bcs_k8s.helm.providers.repo_provider import add_platform_public_repos, add_repo, add_plain_repo
from backend.utils.views import ActionSerializerMixin, FilterByProjectMixin
from backend.components import paas_cc
from backend.utils.views import AccessTokenMixin, ProjectMixin, AppMixin, with_code_wrapper
from backend.bcs_k8s.authtoken.authentication import TokenAuthentication
from backend.utils import client as bcs_utils_client
from backend.components.bcs import k8s
from .utils import collect_resource_state, collect_resource_status, get_base_url, resource_link
from backend.accounts import bcs_perm
from backend.bcs_k8s.bke_client.client import BCSClusterNotFound, BCSClusterCredentialsNotFound
from backend.bcs_k8s.dashboard.exceptions import DashboardError, DashboardExecutionError
from backend.bcs_k8s.app.utils import compose_url_with_scheme
from backend.apps.depot.api import get_jfrog_account
from backend.utils.errcodes import ErrorCode

logger = logging.getLogger(__name__)


class AppViewBase(AccessTokenMixin, ProjectMixin, viewsets.ModelViewSet):
    queryset = App.objects.all()
    lookup_url_kwarg = "app_id"

    def get_queryset(self):
        queryset = super(AppViewBase, self).get_queryset().filter(project_id=self.project_id).order_by("-updated")
        return queryset.exclude()


@with_code_wrapper
class AppView(ActionSerializerMixin, AppViewBase):
    serializer_class = AppSLZ

    action_serializers = {
        'update': AppUpgradeSLZ,
        'retrieve': AppDetailSLZ,
    }

    def get_project_cluster(self, request, project_id):
        """获取项目下集群信息
        """
        project_cluster = paas_cc.get_all_clusters(
            request.user.token.access_token, project_id, desire_all_data=True)
        if project_cluster.get('code') != ErrorCode.NoError:
            logger.error('Request cluster info error, detail: %s' % project_cluster.get('message'))
            return {}
        data = project_cluster.get('data') or {}
        results = data.get('results') or []
        return {info['cluster_id']: info for info in results} if results else {}

    def list(self, request, project_id, *args, **kwargs):
        """
        """
        project_cluster = self.get_project_cluster(request, project_id)
        qs = self.get_queryset()
        data = list(qs.values(
            "name", "id", "cluster_id", "project_id", "namespace", "namespace_id", "version",
            "created", "creator", "chart__id", "transitioning_action", "transitioning_message",
            "transitioning_on", "transitioning_result", "updated", "updator"
        ))

        # do fix on the data which version is emtpy
        datetime_format = "%Y-%m-%d %H:%M:%S"
        for item in data:
            cluster_info = project_cluster.get(item['cluster_id']) or {'name': item['cluster_id']}
            item['cluster_name'] = cluster_info['name']
            item['cluster_env'] = settings.CLUSTER_ENV_FOR_FRONT.get(cluster_info.get('environment'))
            item["current_version"] = item.pop("version")
            if not item["current_version"]:
                version = App.objects.filter(id=item["id"]).values_list(
                    "release__chartVersionSnapshot__version", flat=True)[0]
                App.objects.filter(id=item["id"]).update(version=version)
                item["current_version"] = version

            helm_deploy_timeout = timezone.timedelta(minutes=60)
            if item["transitioning_on"] and (timezone.now() - item["updated"]) > helm_deploy_timeout:
                App.objects.filter(id=item["id"]).update(
                    transitioning_on=False,
                    transitioning_result=False,
                    transitioning_message="Helm操作超时，请重试!",
                )
                item["transitioning_result"] = False
                item["transitioning_on"] = False
                item["transitioning_message"] = "Helm操作超时，请重试!"

            item["chart"] = item.pop("chart__id")
            item["created"] = item["created"].astimezone().strftime(datetime_format)
            item["updated"] = item["updated"].astimezone().strftime(datetime_format)

        result = {
            "count": len(data),
            "next": None,
            "previous": None,
            "results": data
        }
        return Response(data=result)

    def retrieve(self, request, *args, **kwargs):
        app_id = self.request.parser_context["kwargs"]["app_id"]
        if not App.objects.filter(id=app_id).exists():
            return Response({"code": 404, "detail": "app not found"})
        return super(AppView, self).retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        try:
            return super(AppView, self).create(request, *args, **kwargs)
        except IntegrityError as e:
            logger.warning("helm app create IntegrityError, %s", e)
            return Response(status=400, data={
                "code": 400,
                "message": "helm app name already exists in this cluster",
            })
        except BCSClusterNotFound:
            return Response(data={
                "code": 40031,
                "message": "集群未注册",
            })
        except BCSClusterCredentialsNotFound:
            return Response(data={
                "code": 40031,
                "message": "集群证书未上报",
            })

    def destroy(self, request, *args, **kwargs):
        """ 重载默认的 destroy 方法，用于实现判断是否删除成功
        """
        instance = self.get_object()

        check_cluster_perm(
            user=request.user,
            project_id=instance.project_id,
            cluster_id=instance.cluster_id,
            request=request
        )

        self.perform_destroy(instance)

        if App.objects.filter(id=instance.id).exists():
            instance = App.objects.get(id=instance.id)
            data = {
                "transitioning_result": instance.transitioning_result,
                "transitioning_message": instance.transitioning_message,
            }
        else:
            data = {
                "transitioning_result": True,
                "transitioning_message": "success deleted"
            }
        return Response(data)

    def perform_destroy(self, instance):
        instance.destroy(
            username=self.request.user.username,
            access_token=self.access_token
        )


@with_code_wrapper
class AppRollbackView(AppViewBase):
    serializer_class = AppRollbackSLZ


@with_code_wrapper
class AppNamespaceView(AccessTokenMixin, ProjectMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = NamespaceSLZ

    def get_queryset(self):

        result = paas_cc.get_namespace_list(self.access_token, self.project_id)
        results = result["data"]["results"]
        if not results:
            return []
        # 补充cluster_name字段
        cluster_ids = [i['cluster_id'] for i in results]
        cluster_list = paas_cc.get_cluster_list(
            self.access_token, self.project_id, cluster_ids).get('data') or []
        # cluster_list = bcs_perm.Cluster.hook_perms(request, project_id, cluster_list)
        cluster_dict = {i['cluster_id']: i for i in cluster_list}

        for i in results:
            # ns_vars = NameSpaceVariable.get_ns_vars(i['id'], project_id)
            i['ns_vars'] = []

            if i['cluster_id'] in cluster_dict:
                i['cluster_name'] = cluster_dict[i['cluster_id']]['name']
                i['environment'] = cluster_dict[i['cluster_id']]['environment']
            else:
                i['cluster_name'] = i['cluster_id']
                i['environment'] = None

        perm = bcs_perm.Namespace(self.request, self.project_id, bcs_perm.NO_RES)
        results = perm.hook_perms(results, True)
        return results

    def list(self, request, project_id):
        queryset = self.get_queryset()
        if not queryset:
            return Response([])
        cluster_id_name_map = {item["cluster_id"]: item["cluster_name"] for item in queryset}

        # check which namespace has the chart_id initialized
        namespace_ids = []
        chart_id = request.query_params.get("chart_id")
        if chart_id:
            namespace_ids = set(App.objects.filter(
                project_id=self.project_id, chart__id=chart_id
            ).values_list("namespace_id", flat=True))

        serializer = self.serializer_class(queryset, many=True)
        data = serializer.data
        for item in data:
            has_initialized = item["id"] in namespace_ids
            item["has_initialized"] = has_initialized

        # Sort by the desired field first
        data.sort(key=itemgetter('cluster_id'))
        # Iterate in groups
        result = []
        for cluster_id, items in groupby(data, key=itemgetter('cluster_id')):
            result.append({
                "name": "%s(%s)" % (cluster_id_name_map[cluster_id], cluster_id),
                "children": list(items)
            })
        return Response(result)


@with_code_wrapper
class AppUpgradeVersionsView(AppMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = AppUpgradeVersionsSLZ

    def get_queryset(self):
        instance = App.objects.get(id=self.app_id)
        return instance.get_upgrade_version_selections()


@with_code_wrapper
class AppRollbackSelectionsView(AppMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = AppRollbackSelectionsSLZ

    def get_queryset(self):
        instance = App.objects.get(id=self.app_id)
        return instance.get_history_releases()


@with_code_wrapper
class AppReleaseDiffView(viewsets.ModelViewSet):
    serializer_class = AppReleaseDiffSLZ


@with_code_wrapper
class AppReleasePreviewView(AccessTokenMixin, ProjectMixin, viewsets.ModelViewSet):
    serializer_class = AppReleasePreviewSLZ


@with_code_wrapper
class AppRollbackPreviewView(AppMixin, AccessTokenMixin, ProjectMixin, viewsets.ModelViewSet):
    serializer_class = AppRollbackPreviewSLZ


@with_code_wrapper
class AppPreviewView(AppMixin, AccessTokenMixin, ProjectMixin, viewsets.ModelViewSet):
    serializer_class = AppPreviewSLZ

    def get_object(self):
        instance = App.objects.get(id=self.app_id)
        content, notes = instance.render_app(
            username=self.request.user.username,
            access_token=self.access_token)
        return {
            "content": content,
            "notes": notes,
            "token": self.access_token
        }


@with_code_wrapper
class AppStructureView(AppMixin, AccessTokenMixin, ProjectMixin, viewsets.ModelViewSet):
    serializer_class = AppPreviewSLZ

    def retrieve(self, request, *args, **kwargs):
        base_url = get_base_url(request)
        instance = App.objects.get(id=self.app_id)
        content = instance.release.content
        resources = parser.parse(content, instance.namespace).values()
        data = []
        # request.META.HTTP_REFERER
        # raise ValueError(request.META)
        for resource in resources:
            resource_dict = yaml.load(resource.content)
            url = resource_link(
                base_url=base_url,
                kind=resource.kind.lower(),
                name=resource_dict["metadata"]["name"],
                namespace=instance.namespace,
                release_name=instance.name
            )
            item = {
                "link": url,
                "namespace": instance.namespace,
                "name": resource_dict["metadata"]["name"],
                "kind": resource.kind.lower(),
            }
            data.append(item)
        return Response({"data": data})


@with_code_wrapper
class AppCreatePreviewView(AccessTokenMixin, ProjectMixin, viewsets.ModelViewSet):
    serializer_class = AppCreatePreviewSLZ


@with_code_wrapper
class AppCreatePreviewDiffWithClusterView(AccessTokenMixin, ProjectMixin, viewsets.ModelViewSet):
    serializer_class = AppCreatePreviewDiffWithClusterSLZ


@with_code_wrapper
class AppUpdateChartVersionView(AppMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = ChartVersionSLZ
    lookup_url_kwarg = "update_chart_version_id"

    def retrieve(self, request, *args, **kwargs):
        app = App.objects.get(id=self.app_id)
        update_chart_version_id = int(self.request.parser_context["kwargs"]["update_chart_version_id"])
        if update_chart_version_id == -1:
            chart_version_snapshot = app.release.chartVersionSnapshot
            chart_version = ChartVersion(
                id=0,
                chart=app.chart,
                keywords="mocked chart version",
                version=chart_version_snapshot.version,
                digest=chart_version_snapshot.digest,
                name=chart_version_snapshot.name,
                home=chart_version_snapshot.home,
                description=chart_version_snapshot.description,
                engine=chart_version_snapshot.engine,
                created=chart_version_snapshot.created,
                maintainers=chart_version_snapshot.maintainers,
                sources=chart_version_snapshot.sources,
                urls=chart_version_snapshot.urls,
                files=chart_version_snapshot.files,
                questions=chart_version_snapshot.questions,
            )
        else:
            chart_version = ChartVersion.objects.get(id=update_chart_version_id)
        slz = self.serializer_class(chart_version)
        return Response(slz.data)


def render_bcs_agent_template(token, bcs_cluster_id, namespace, access_token, project_id, cluster_id):
    bcs_server_host = bcs_utils_client.get_bcs_host(access_token, project_id, cluster_id)
    token = base64.b64encode(str.encode(token))

    # 除 prod 环境外，其它环境都的bcs agent名称都带 环境前缀
    prefix = ""
    if settings.HELM_REPO_ENV != "prod":
        prefix = "%s-" % settings.HELM_REPO_ENV

    render_context = {
        'prefix': prefix,
        'namespace': namespace,
        'token': str(token, encoding='utf-8'),
        'bcs_address': bcs_server_host,
        'bcs_cluster_id': str(bcs_cluster_id),
        'hub_host': settings.DEVOPS_ARTIFACTORY_HOST
    }
    return render_to_string('bcs_agent_tmpl.yaml', render_context)


@with_code_wrapper
class ClusterImporterView(AccessTokenMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = ClusterImportSLZ

    @property
    def bcs_agent_namespace(self):
        return "kube-system"

    def create(self, request, project_id, *args, **kwargs):
        serializer = ClusterImportSLZ(data=request.data)
        serializer.is_valid(raise_exception=True)

        cluster_id = serializer.data["cluster_id"]

        check_cluster_perm(
            user=request.user,
            project_id=project_id,
            cluster_id=cluster_id,
            request=request
        )

        bcs_client = bcs_utils_client.get_bcs_client(
            project_id=project_id,
            cluster_id=cluster_id,
            access_token=self.access_token
        )
        bcs_cluster_info = bcs_client.get_or_register_bcs_cluster()
        if not bcs_cluster_info["result"]:
            return Response(data=bcs_cluster_info)

        bcs_cluster_info = bcs_cluster_info["data"]
        content = render_bcs_agent_template(
            token=bcs_cluster_info["token"],
            bcs_cluster_id=bcs_cluster_info["bcs_cluster_id"],
            namespace=self.bcs_agent_namespace,
            access_token=self.access_token,
            project_id=project_id,
            cluster_id=cluster_id
        )

        response = HttpResponse(content=content, content_type='text/plain; charset=UTF-8')
        response['Content-Disposition'] = 'attachment; filename="bcs-agent-%s.yaml"' % cluster_id
        return response


@with_code_wrapper
class ClusterKubeConfigView(AccessTokenMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = ClusterKubeConfigSLZ

    def create(self, request, project_id, *args, **kwargs):
        serializer = ClusterKubeConfigSLZ(data=request.data)
        serializer.is_valid(raise_exception=True)

        cluster_id = serializer.data["cluster_id"]

        check_cluster_perm(
            user=request.user,
            project_id=project_id,
            cluster_id=cluster_id,
            request=request
        )

        kubeconfig = bcs_utils_client.get_kubectl_config_context(
            access_token=self.access_token,
            project_id=project_id,
            cluster_id=cluster_id
        )

        response = HttpResponse(content=kubeconfig, content_type='text/plain; charset=UTF-8')
        response['Content-Disposition'] = 'attachment; filename="bcs-%s-kubeconfig.yaml"' % cluster_id
        return response


@with_code_wrapper
class SyncDict2YamlToolView(viewsets.ModelViewSet):
    serializer_class = SyncDict2YamlToolSLZ


@with_code_wrapper
class SyncYaml2DictToolView(viewsets.ModelViewSet):
    serializer_class = SyncYaml2DictToolSLZ


@with_code_wrapper
class ClusterHelmInitView(ClusterImporterView):
    serializer_class = ClusterHelmInitSLZ

    def get_or_add_public_repos(self, project_id):
        if not settings.HELM_HAS_ABILITY_SUPPLY_CHART_REPO_SERVICE:
            return []

        # 1. add/get plain public repo for project
        public_repos = add_platform_public_repos(target_project_id=project_id)
        return public_repos

    def get_or_add_private_repos(self, project_id, user):
        project = paas_cc.get_project(access_token=self.access_token, project_id=project_id)
        if settings.HELM_HAS_ABILITY_SUPPLY_CHART_REPO_SERVICE:
            # 2. add/get private repo for project
            private_repo = add_repo(
                target_project_id=project_id,
                name=project["data"]["english_name"],
                provider_name="chartmuseum",
                url="http://localhost/",  # merely provide schema
                user=user,
            )
        else:
            repo_auth = {
                "type": "basic",
                "role": "admin",
                "credentials": {
                    "username": settings.HELM_MERELY_REPO_USERNAME,
                    "password": settings.HELM_MERELY_REPO_PASSWORD,
                }
            }
            english_name = project['data']['english_name']
            url = '%s/chartrepo/%s/' % (settings.HELM_MERELY_REPO_URL, english_name)
            private_repo = add_plain_repo(
                target_project_id=project_id,
                name=english_name,
                url=url,
                repo_auth=repo_auth
            )
        return [private_repo]

    def retrieve(self, request, project_id, *args, **kwargs):
        parameter = dict(request.GET.items())
        serializer = ClusterKubeConfigSLZ(data=parameter)
        serializer.is_valid(raise_exception=True)

        cluster_id = serializer.data["cluster_id"]

        check_cluster_perm(
            user=request.user,
            project_id=project_id,
            cluster_id=cluster_id,
            request=request
        )

        if settings.HELM_HAS_ABILITY_SUPPLY_CHART_REPO_SERVICE:
            bcs_client = bcs_utils_client.get_bcs_client(
                project_id=project_id,
                cluster_id=cluster_id,
                access_token=self.access_token
            )

            bcs_cluster_info = bcs_client.get_cluster()
            if bcs_cluster_info is None or not bcs_cluster_info.get("bcs_cluster_id"):
                result = {
                    "code": 17602,
                    "message": "cluster does not regist to bcs yet.",
                    "initialized": False
                }
                return Response(result)

        serializer = self.serializer_class({
            "public_repos": self.get_or_add_public_repos(project_id),
            "private_repos": self.get_or_add_private_repos(project_id, request.user),
            "initialized": True
        })
        return Response(data=serializer.data)

    def create(self, request, project_id, *args, **kwargs):
        serializer = ClusterKubeConfigSLZ(data=request.data)
        serializer.is_valid(raise_exception=True)

        cluster_id = serializer.data["cluster_id"]

        check_cluster_perm(
            user=request.user,
            project_id=project_id,
            cluster_id=cluster_id,
            request=request
        )

        # 检查是否有 node, 没有node时，bcs-agent无法启动
        nodes_info = paas_cc.get_node_list(self.access_token, project_id, cluster_id)
        if not nodes_info["data"]["results"]:
            return Response(data={
                "code": 40032,
                "message": "集群下没有Node节点，无法启用，请先添加"
            })
        data = helm_init(self.access_token, project_id, cluster_id, self.bcs_agent_namespace)

        return Response(data=data)


def helm_init(access_token, project_id, cluster_id, bcs_agent_namespace):
    if not settings.HELM_NEED_REGIST_TO_BKE_WHEN_INIT:
        data = {
            "code": 0,
            "initialized": True,
            "detail": "HELM_NEED_REGIST_TO_BKE_WHEN_INIT set",
            "message": "ok",
        }
        return data

    # 1. do registering to bcs
    # need to be re-entrant
    bcs_client = bcs_utils_client.get_bcs_client(
        project_id=project_id,
        cluster_id=cluster_id,
        access_token=access_token
    )
    bcs_cluster_info = bcs_client.get_or_register_bcs_cluster()
    if not bcs_cluster_info.get("result"):
        data = {
            "code": 10601,
            "message": "failed to regist to bcs.",
            "data": bcs_cluster_info
        }
        return Response(data=data)

    bcs_cluster_info = bcs_cluster_info["data"]
    content = render_bcs_agent_template(
        token=bcs_cluster_info["token"],
        bcs_cluster_id=bcs_cluster_info["bcs_cluster_id"],
        namespace="kube-system",  # namespace for bcs agent
        access_token=access_token,
        project_id=project_id,
        cluster_id=cluster_id
    )
    resources = parser.parse(content, bcs_agent_namespace).values()

    # 2. apply bcs agent deploy resource to target cluster
    # need to be re-entrant
    client = k8s.K8SClient(access_token, project_id, cluster_id, env=None)

    errors = []
    for item in resources:
        if item.kind != "Secret":
            continue

        data = yaml.load(item.content)
        result = client.create_secret(bcs_agent_namespace, data)
        if result["code"] == 0:
            continue
        if not (result["code"] == 4001 and "exists" in result["message"]):
            errors.append("create_secret, %s" % json.dumps(result))
            logger.error("ClusterHelmInitView client.create_secret, %s", json.dumps(result))

    for item in resources:
        if item.kind != "ServiceAccount":
            continue

        data = yaml.load(item.content)
        result = client.create_serviceaccounts(bcs_agent_namespace, data)
        if result["code"] == 0:
            continue
        if not (result["code"] == 4001 and "exists" in result["message"]):
            errors.append("create_serviceaccounts, %s" % json.dumps(result))
            logger.error("ClusterHelmInitView client.create_serviceaccounts, %s", json.dumps(result))

    for item in resources:
        if item.kind != "ClusterRoleBinding":
            continue

        data = yaml.load(item.content)
        result = client.create_clusterrolebindings(bcs_agent_namespace, data)
        if result["code"] == 0:
            continue
        if not (result["code"] == 4001 and "exists" in result["message"]):
            errors.append("create_clusterrolebindings, %s" % json.dumps(result))
            logger.error("ClusterHelmInitView client.create_clusterrolebindings, %s", json.dumps(result))

    for item in resources:
        if item.kind != "Deployment":
            continue

        data = yaml.load(item.content)
        result = client.create_deployment(bcs_agent_namespace, data)
        if result["code"] == 0:
            continue
        if not (result["code"] == 4001 and "exists" in result["message"]):
            errors.append("create_deployment, %s" % json.dumps(result))
            logger.error("ClusterHelmInitView client.create_deployment, %s", json.dumps(result))

    # step3 and step4 has been moved to enable container service
    # 3. add plain public repo for project
    # public_repos = self.get_or_add_public_repos(project_id)

    # 4. add private repo for project
    # private_repos = self.get_or_add_private_repos(project_id, request.user)

    data = {
        "code": 0 if not bool(errors) else 400,
        "initialized": not bool(errors),
        "detail": errors,
        "message": "\n\n".join(errors),
    }
    return data


@with_code_wrapper
class AppStateView(AppMixin, AccessTokenMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = AppStateSLZ
    lookup_url_kwarg = "app_id"

    def retrieve(self, request, app_id, *args, **kwargs):
        app = App.objects.get(id=self.app_id)

        check_cluster_perm(
            user=request.user,
            project_id=app.project_id,
            cluster_id=app.cluster_id,
            request=request
        )

        content = app.release.content
        # resources = parser.parse(content, app.namespace)
        with bcs_utils_client.make_kubectl_client(
            access_token=self.access_token,
            project_id=app.project_id,
            cluster_id=app.cluster_id
        ) as (client, err):
            if err:
                raise APIException(str(err))

            state = collect_resource_state(
                kube_client=client, namespace=app.namespace, content=content)

        return Response(state)


@with_code_wrapper
class AppStatusView(AppMixin, AccessTokenMixin, viewsets.ReadOnlyModelViewSet, ProjectMixin):
    serializer_class = AppStateSLZ
    lookup_url_kwarg = "app_id"

    def retrieve(self, request, app_id, *args, **kwargs):
        app = App.objects.get(id=self.app_id)

        project_code_cache_key = "helm_project_cache_key:%s" % self.project_id
        if project_code_cache_key in cache:
            resp = cache.get(project_code_cache_key)

        else:
            # get_project_name
            resp = paas_cc.get_project(self.access_token, self.project_id)
            if resp.get('code') != 0:
                logger.error("查询project的信息出错(project_id:{project_id}):{message}".format(
                    project_id=self.project_id,
                    message=resp.get('message'))
                )
                return Response({
                    "code": 500,
                    "message": "后台接口异常，根据项目ID获取项目英文名失败！"
                })

            cache.set(project_code_cache_key, resp, 60 * 15)

        project_code = resp["data"]["english_name"]

        check_cluster_perm(
            user=request.user,
            project_id=app.project_id,
            cluster_id=app.cluster_id,
            request=request
        )

        kubeconfig = bcs_utils_client.get_kubectl_config_context(
            access_token=self.access_token,
            project_id=app.project_id,
            cluster_id=app.cluster_id
        )

        base_url = get_base_url(request)
        try:
            with tempfile.NamedTemporaryFile("w") as f:
                f.write(kubeconfig)
                f.flush()

                data = collect_resource_status(
                    base_url=base_url,
                    kubeconfig=f.name,
                    app=app,
                    project_code=project_code
                )
        except DashboardExecutionError as e:
            message = "get helm app status failed, error_no: {error_no}\n{output}".format(
                error_no=e.error_no,
                output=e.output
            )
            return Response({
                "code": 400,
                "message": message,
            })
        except DashboardError as e:
            message = "get helm app status failed, dashboard ctl error: {err}".format(err=e)
            logger.exception(message)
            return Response({
                "code": 400,
                "message": message,
            })
        except Exception as e:
            message = "get helm app status failed, {err}".format(err=e)
            logger.exception(message)
            return Response({
                "codee": 500,
                "message": message,
            })

        response = {
            "status": data,
            "app": {
                "transitioning_action": app.transitioning_action,
                "transitioning_on": app.transitioning_on,
                "transitioning_result": app.transitioning_result,
                "transitioning_message": app.transitioning_message,
            },
        }
        return Response(response)


@with_code_wrapper
class AppAPIView(viewsets.ModelViewSet):
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = AppUpgradeByAPISLZ
    lookup_url_kwarg = "app_id"
    queryset = App.objects.all()


class HowToPushHelmChartView(AccessTokenMixin, viewsets.GenericViewSet):

    def create_private_repo_without_chart(self, user, project_id, project_code):
        # 通过harbor api创建一次项目账号，然后存储在auth中
        private_repos = Repository.objects.filter(name=project_code, project_id=project_id)
        if private_repos.exists():
            return private_repos[0]
        account = get_jfrog_account(self.access_token, project_code, project_id)
        repo_auth = {
            "type": "basic",
            "role": "admin",
            "credentials": {
                # "username": settings.HELM_MERELY_REPO_USERNAME,
                # "password": settings.HELM_MERELY_REPO_PASSWORD,
                "username": account.get("user"),
                "password": account.get("password")
            }
        }
        url = '%s/chartrepo/%s/' % (settings.HELM_MERELY_REPO_URL, project_code)
        private_repo = add_plain_repo(
            target_project_id=project_id,
            name=project_code,
            url=url,
            repo_auth=repo_auth
        )
        return private_repo

    def get_private_repo_info(self, user, project_id, project_code):
        # project = paas_cc.get_project(access_token=self.access_token, project_id=project_id)
        # english_name = project['data']['english_name']
        if settings.HELM_HAS_ABILITY_SUPPLY_CHART_REPO_SERVICE:
            # 2. add/get private repo for project
            private_repo = add_repo(
                target_project_id=project_id,
                name=project_code,
                provider_name="chartmuseum",
                url="http://localhost/",  # merely provide schema
                user=user,
            )
        else:
            private_repo = self.create_private_repo_without_chart(user, project_id, project_code)

        if not private_repo.plain_auths:
            return {
                "url": "",
                "username": "",
                "password": "",
            }
        repo_info = private_repo.plain_auths[0]["credentials"]
        repo_info["url"] = private_repo.url
        return repo_info

    def retrieve(self, request, project_id, *args, **kwargs):
        project = paas_cc.get_project(access_token=request.user.token.access_token, project_id=project_id)
        project_code = project["data"]["english_name"]
        repo_info = self.get_private_repo_info(
            user=request.user, project_id=project_id, project_code=project_code)

        base_url = request.build_absolute_uri()
        base_url = base_url.split("bcs/k8s")[0]
        if not settings.HELM_HAS_ABILITY_SUPPLY_CHART_REPO_SERVICE:
            repo_url = repo_info["url"]
        else:
            repo_url = f"http://{settings.PLATFORM_REPO_DOMAIN}/{settings.HELM_REPO_ENV}/{project_code}"

        context = {
            "project_id": project_id,
            "chart_domain": settings.PLATFORM_REPO_DOMAIN,
            "helm_env": settings.HELM_REPO_ENV,
            "project_code": str(project_code),
            "username": repo_info["username"],
            "password": repo_info["password"],
            "base_url": base_url,
            "repo_url": repo_url,
            "helm_push_parameters": "",
            "rumpetroll_demo_url": settings.RUMPETROLL_DEMO_DOWNLOAD_URL
        }

        if settings.HELM_HAS_ABILITY_SUPPLY_CHART_REPO_SERVICE:
            context["helm_push_parameters"] = "--context-path=/{helm_env}/{project_code}".format(
                helm_env=settings.HELM_REPO_ENV,
                project_code=str(project_code)
            )

        filename = "backend/bcs_k8s/app/documentation/how-to-push-chart.md"
        with open(os.path.join(settings.STATIC_ROOT.split("staticfiles")[0], filename), "r") as f:
            template = Template(f.read())

        content = template.render(**context)
        response = HttpResponse(content=content, content_type='text/plain; charset=UTF-8')
        response['Content-Disposition'] = 'attachment; filename="how-to-push-helm-chart.md"'
        return response


@with_code_wrapper
class ContainerRegistryDomainView(AccessTokenMixin, ProjectMixin, viewsets.ViewSet):
    def retrieve(self, request, project_id, *args, **kwargs):
        cluster_id = request.query_params.get("cluster_id")

        check_cluster_perm(
            user=request.user,
            project_id=project_id,
            cluster_id=cluster_id,
            request=request
        )

        # 获取镜像地址
        jfrog_domain = paas_cc.get_jfrog_domain(
            access_token=self.access_token,
            project_id=self.project_id,
            cluster_id=cluster_id
        )

        cluster_info = paas_cc.get_cluster(
            request.user.token.access_token, project_id, cluster_id)["data"]

        context = dict(
            cluster_id=cluster_id,
            cluster_name=cluster_info["name"],
            jfrog_domain=jfrog_domain,
            expr="{{ .Values.__BCS__.SYS_JFROG_DOMAIN }}",
            link=settings.HELM_DOC_TRICKS
        )
        note = ("集群：{cluster_name}({cluster_id}) 的容器仓库域名为: {jfrog_domain}, "
                "可在Chart直接引用 `{expr}` "
                "更加方便, [详细说明]({link})").format(**context)
        context["note"] = note
        return Response(data=context)


@with_code_wrapper
class ClearAppInjectDataView(AccessTokenMixin, ProjectMixin, viewsets.ModelViewSet):
    serializer_class = Serializer
    queryset = App.objects.all()
    lookup_url_kwarg = "app_id"

    def update(self, request, project_id, app_id, *args, **kwargs):
        app = self.queryset.get(project_id=project_id, id=app_id)

        check_cluster_perm(
            user=request.user,
            project_id=app.project_id,
            cluster_id=app.cluster_id,
            request=request
        )

        app.inject_configs = None
        app.save(update_fields=["inject_configs"])
        return Response(data={"code": 0, "message": "ok"})


@with_code_wrapper
class AppTransiningView(AppViewBase):
    def retrieve(self, request, *args, **kwargs):
        app_id = self.request.parser_context["kwargs"]["app_id"]
        if not App.objects.filter(id=app_id).exists():
            return Response({"code": 404, "detail": "app not found"})

        app = App.objects.get(id=app_id)
        data = {
            "transitioning_action": app.transitioning_action,
            "transitioning_on": app.transitioning_on,
            "transitioning_result": app.transitioning_result,
            "transitioning_message": app.transitioning_message,
        }
        response = {
            "code": 0,
            "message": "ok",
            "data": data,
        }
        return Response(response)
