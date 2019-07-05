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

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from backend.apps.network.models import K8SLoadBlance
from backend.utils.error_codes import error_codes
from backend.apps.configuration.serializers import RE_NAME
from backend.apps.network.constants import MESOS_LB_NAMESPACE_NAME
from django.core.validators import MaxValueValidator, MinValueValidator


class BatchResourceSLZ(serializers.Serializer):
    data = serializers.JSONField(required=True)

    def validate_data(self, data):
        if not isinstance(data, list):
            raise ValidationError(u"数据格式必须为数组")
        for _d in data:
            if not _d.get('cluster_id'):
                raise ValidationError(u"cluster_id 必填")
            if not _d.get('namespace'):
                raise ValidationError(u"namespace 必填")
            if not _d.get('name'):
                raise ValidationError(u"name 必填")
        return data


class NginxIngressSLZ(serializers.ModelSerializer):
    project_id = serializers.CharField(max_length=32, required=True)
    cluster_id = serializers.CharField(max_length=32, required=True)
    namespace_id = serializers.IntegerField(required=True)
    name = serializers.CharField(max_length=32, required=True)
    protocol_type = serializers.CharField(max_length=32, required=True)
    ip_info = serializers.JSONField(required=True)
    detail = serializers.JSONField(required=False)
    creator = serializers.CharField(max_length=16, required=False)
    updator = serializers.CharField(max_length=16, required=False)

    def validate_protocol_type(self, value):
        type_list = re.findall(r"[^,; ]+", value)
        protocol_port_list = []
        for info in type_list:
            protocol_port_list.extend(info.split(":"))
        if "http" not in protocol_port_list and "https" not in protocol_port_list:
            raise ValidationError("参数【protocol_type】至少包含http或https，请确认后重试!")
        return value

    class Meta:
        model = K8SLoadBlance
        fields = (
            "id",
            "project_id",
            "cluster_id",
            "namespace_id",
            "name",
            "protocol_type",
            "ip_info",
            "detail",
            "creator",
            "updator",
            "is_deleted",
        )


class NginxIngressUpdateSLZ(serializers.Serializer):
    id = serializers.IntegerField(required=True)
    protocol_type = serializers.CharField(max_length=32, required=True)
    ip_info = serializers.JSONField(required=True)
    updator = serializers.CharField(max_length=16, required=True)


class LoadBalancesSLZ(serializers.Serializer):
    """创建LB
    """
    name = serializers.RegexField(
        RE_NAME,
        max_length=256,
        required=True,
        error_messages={
            'invalid': u'名称格式错误，只能包含：小写字母、数字、连字符(-)，首字母必须是字母，长度小于256个字符'
        }
    )
    cluster_id = serializers.CharField(required=True)
    instance = serializers.IntegerField(required=False, default=1)
    ip_list = serializers.JSONField(required=False, default=[])
    constraints = serializers.JSONField(required=True)
    # type = serializers.ChoiceField(choices=['cover', 'append'], required=True)
    # mesos lb限制使用的lb占用的命名空间只能作为lb使用，并且建议全局使用同一个命名空间
    namespace = serializers.CharField(required=False, default=MESOS_LB_NAMESPACE_NAME)
    namespace_id = serializers.IntegerField(required=False, default=-1)
    network_type = serializers.CharField(required=True)
    network_mode = serializers.CharField(required=True)
    custom_value = serializers.CharField(required=False, allow_blank=True)
    image_url = serializers.CharField(required=True)
    image_version = serializers.CharField(required=True)
    resources = serializers.JSONField(required=True)
    forward_mode = serializers.CharField(required=True)
    eth_value = serializers.CharField(required=True)
    host_port = serializers.IntegerField(
        required=False,
        default=31000,
        validators=[MaxValueValidator(32000), MinValueValidator(31000)]
    )

    def validate_constraints(self, constraints):
        """测试数据
        """
        return constraints

    def validate_instance(self, instance):
        """当instance和ip_list都存在时，要校验两者数量相同
        """
        data = self._kwargs.get('data', {})
        ip_list = data.get('ip_list')
        if not ip_list:
            return instance
        if len(ip_list) != instance:
            raise error_codes.CheckFailed.f("参数[ip_list]和[instance]必须相同")
        return instance


class UpdateLoadBalancesSLZ(LoadBalancesSLZ):
    """更新值
    """

    def validate(self, data):
        if not data:
            raise ValidationError("参数不能全部为空")
        return data


class GetLoadBalanceSLZ(serializers.Serializer):
    limit = serializers.IntegerField(required=True)
    offset = serializers.IntegerField(required=True)


class ServiceListSLZ(serializers.Serializer):
    limit = serializers.IntegerField(default=10)
    offset = serializers.IntegerField(default=0)
    search_name = serializers.CharField(default='')
    cluster_id = serializers.CharField(default='ALL')
