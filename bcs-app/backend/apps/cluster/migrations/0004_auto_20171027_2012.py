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
# Generated by Django 1.11.5 on 2017-10-27 12:12
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cluster', '0003_auto_20171027_1104'),
    ]

    operations = [
        migrations.AddField(
            model_name='clusterinstalllog',
            name='token',
            field=models.CharField(max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='nodeupdatelog',
            name='token',
            field=models.CharField(max_length=64, null=True),
        ),
    ]
