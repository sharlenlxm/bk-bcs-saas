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
from django.conf.urls import url
from backend.activity_log import views

urlpatterns = [
    url(r'^api/activity_logs/project/(?P<project_id>\w+)/?$', views.LogView.as_view()),
    url(r'^api/activity_events/project/(?P<project_id>\w+)/?$', views.ActivityEventView.as_view()),
    url(r'^api/activity_logs/resource_types/?$', views.ResourceTypesView.as_view()),
    url(r'^api/activity_logs/metadata/$', views.MetaDataView.as_view()),
]
