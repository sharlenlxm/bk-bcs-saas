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
import re

from jsonschema import ValidationError as JsonValidationError, SchemaError, validate as json_validate
from rest_framework.exceptions import ValidationError

from backend.utils.basic import getitems
from backend.apps.configuration import models
from .constants import AFFINITY_SCHEMA, CONFIG_SCHEMA_MAP

K8S_NAME_REGEX = re.compile(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$')
K8S_NAME_ERROR_MSG = "名称格式错误，以小写字母或数字开头，只能包含：小写字母、数字、连字符(-)、点(.)"


def get_config_schema(resource_name):
    return CONFIG_SCHEMA_MAP[resource_name]


def validate_k8s_res_name(name):
    if not K8S_NAME_REGEX.match(name):
        raise ValidationError(K8S_NAME_ERROR_MSG)


def validate_pod_selector(config):
    """检查 selector 是否在label中
    """
    spec = config.get('spec', {})
    selector_labels = getitems(spec, ['selector', 'matchLabels'])
    if selector_labels:
        pod_labels = getitems(spec, ['template', 'metadata', 'labels'], default={})
        if not set(selector_labels.items()).issubset(pod_labels.items()):
            invalid_label_list = ['%s:%s' % (x, pod_labels[x]) for x in pod_labels]
            invalid_label_str = "; ".join(invalid_label_list)
            raise ValidationError(f"[{invalid_label_str}]不在用户填写的标签中")


def validate_affinity(config):
    """检查亲和性
    """
    affinity = getitems(config, ['spec', 'template', 'spec', 'affinity'], default={})
    err_prefix = "亲和性约束配置出错"
    try:
        json_validate(affinity, AFFINITY_SCHEMA)
    except JsonValidationError as e:
        raise ValidationError(f'{err_prefix}:{e.message}')
    except SchemaError as e:
        raise ValidationError(f'{err_prefix}:{e}')


def validate_service_tag(data):
    version_id = data['version_id']
    if not version_id:
        raise ValidationError("请先创建 Service ，再创建 StatefulSet")

    service_tag = data['service_tag']
    if not service_tag:
        raise ValidationError("StatefulSet模板中，请选择关联的 Service")

    try:
        ventity = models.VersionedEntity.objects.get(id=version_id)
    except Exception:
        raise ValidationError(f"模板集版本(id:{version_id})不存在")

    svc_list = ventity.get_k8s_services()
    svc_tag_list = [svc.get('service_tag') for svc in svc_list]

    if service_tag not in svc_tag_list:
        raise ValidationError(f"关联的 Service (service_tag: {service_tag}) 不合法")
