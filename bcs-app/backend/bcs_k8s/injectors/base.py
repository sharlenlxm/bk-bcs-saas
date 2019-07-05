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
import logging
import copy
from dataclasses import dataclass
import re

from . import dpath

logger = logging.getLogger(__name__)


class Matcher:
    """ A matcher is used to indicate whether we should inject data to target resoruce.
    """
    def match(self, resource):
        raise NotImplemented

    def get_kind(self, resource):
        return resource.get("kind")


@dataclass
class KindMatcher(Matcher):
    """Simple KindMatcher compare resource kind with self.kind
    """
    kind: str

    PATTERN_TYPE = type(re.compile(""))

    def match(self, resource):
        resource_kind = self.get_kind(resource)
        kind = self.kind

        if isinstance(kind, str):
            return self.kind == resource_kind
        else:
            raise TypeError(kind)


@dataclass
class ReKindMatcher(Matcher):
    """Simple ReKindMatcher compare resource kind with self.kind of re expression
    """
    kind: str

    PATTERN_TYPE = type(re.compile(""))

    def match(self, resource):
        resource_kind = self.get_kind(resource)
        kind = self.kind

        if isinstance(kind, (str, bytes)):
            if resource_kind is None:
                return False
            return re.compile(kind).match(resource_kind)
        else:
            raise TypeError(kind)


class BaseInjector:
    def __init__(self, matcher, path, data, force_str=False):
        self.matcher = matcher
        # target position to inject
        # path example:
        #    `metadata/annotations`
        #    `spec/containers/\*/env`
        self.path = path
        self.force_str = force_str
        # data example:
        # 1.  {"name": "POD_NAME", "valueFrom": {"apiVersion": "v1", "fieldPath": "metadata.name"}}
        # 2.  {"name": "POD_NAME", "valueFrom": {"apiVersion": "v1", "fieldPath": "metadata.name"}}
        self._data = data

    def filter(self, resource):
        return self.matcher.match(resource)

    def do_inject(self, resource, context=None):
        """
        Inject self.context to target of self.path
        As resource maybe don't contains target path, we use dict merge method to impletes it.
        """
        data = self.get_inject_data(resource, context)
        logger.debug("get_inject_data ret: %s" % data)
        if self.force_str:
            data = self.ensure_value_str(data)

        dpath.merge_to_path(resource, self.path, data)
        return resource

    @staticmethod
    def ensure_value_str(data):
        """ 确保所有的值字段最终都是str，对于可执行的类型，封装返回为str类型
        """
        def wrap_callable_with_ret_str(f):
            def func(*args, **kwargs):
                result = f(*args, **kwargs)
                return str(result)
            return func

        def recursive_wrap(data):
            if isinstance(data, dict):
                return {k: recursive_wrap(v) for k, v in data.items()}
            elif isinstance(data, list):
                return [recursive_wrap(v) for v in data]
            elif callable(data):
                return wrap_callable_with_ret_str(data)
            else:
                return str(data)

        return recursive_wrap(data)

    def get_inject_data(self, resource, context):
        """ replace all callable value with it's run result
        """
        def recursive_replace(d):
            if isinstance(d, dict):
                return {k: recursive_replace(v) for k, v in d.items()}
            elif isinstance(d, list):
                return [recursive_replace(v) for v in d]
            elif callable(d):
                return d(resource, context)
            else:
                return d

        return recursive_replace(self._data)


class InjectManager:
    def __init__(self, configs, resources, context=None):
        """
        configs example:
        [{
            "matchers": [{
                "type": "KindMatcher",
                "parameters": {"kind": "Deployment"}
            }],
            "paths": ["metadata/annotations", "metadata/spec/template/metadata/annotations"]
            "data": {
                "io.tencent.paas.source_type": "helm"
            }
        }]
        """
        self.configs = configs
        self.resources = resources
        self.context = context or dict()

    def do_inject(self):
        for idx, resource in enumerate(self.resources):
            # we do inject resource one by one
            for config in self.configs:
                resource = self.do_config_inject(config, resource)

            self.resources[idx] = resource
        return self.resources

    def do_config_inject(self, config, resource):
        for path in config["paths"]:
            for matcher_cfg in config["matchers"]:
                matcher = self.make_matcher(matcher_cfg)
                injector = BaseInjector(
                    matcher=matcher,
                    path=path,
                    data=config["data"]
                )
                if injector.filter(resource):
                    resource = injector.do_inject(resource, self.context)

        return resource

    def make_matcher(self, matcher_cfg):
        if matcher_cfg["type"] == "KindMatcher":
            return KindMatcher(**matcher_cfg["parameters"])
        elif matcher_cfg["type"] == "ReKindMatcher":
            return ReKindMatcher(**matcher_cfg["parameters"])
        else:
            raise ValueError(matcher_cfg["type"])
