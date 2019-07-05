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
# Generated by Django 1.11.5 on 2017-10-28 09:31
from __future__ import unicode_literals

from django.db import migrations, models


def unique_temps_names(apps, schema_editor):
    # 将已有的模板名称都加上id后缀，保证名称的唯一性
    Template = apps.get_model('configuration', 'Template')
    temps = Template.objects.all()
    for tem in temps:
        tem.name = '%s&%s' % (tem.name, tem.id)
        tem.save()


class Migration(migrations.Migration):

    dependencies = [
        ('configuration', '0003_deplpyment_name'),
    ]

    operations = [
        migrations.RunPython(unique_temps_names),
        migrations.AlterField(
            model_name='template',
            name='name',
            field=models.CharField(max_length=32, unique=True, verbose_name='名称'),
        ),
    ]
