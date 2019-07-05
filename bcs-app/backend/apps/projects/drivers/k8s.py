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

from backend.bcs_k8s.helm.providers import repo_provider
from backend.bcs_k8s.helm.tasks import sync_helm_repo

logger = logging.getLogger(__name__)


class K8SDriver:

    @classmethod
    def backend_create_helm_info(cls, project_id):
        try:
            repo_list = repo_provider.add_platform_public_repos(project_id)
            sync_helm_repo.delay(repo_list[0].id, force=True)
        except Exception as err:
            logger.error("添加项目Helm仓库失败，详细信息: %s", err)
