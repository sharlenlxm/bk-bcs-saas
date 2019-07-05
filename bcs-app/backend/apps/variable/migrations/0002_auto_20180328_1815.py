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
# Generated by Django 1.11.5 on 2018-03-28 10:15
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('variable', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='NameSpaceVariable',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creator', models.CharField(max_length=32, verbose_name='创建者')),
                ('updator', models.CharField(max_length=32, verbose_name='更新者')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('deleted_time', models.DateTimeField(blank=True, null=True)),
                ('var_id', models.IntegerField(verbose_name='变量ID')),
                ('ns_id', models.IntegerField(verbose_name='命名空间ID')),
                ('data', models.TextField(help_text="以{'value':'值'}格式存储默认值,可以存储字符串和数字", verbose_name='值')),
            ],
            options={
                'ordering': ('id',),
            },
        ),
        migrations.AlterUniqueTogether(
            name='namespacevariable',
            unique_together=set([('var_id', 'ns_id')]),
        ),
    ]
