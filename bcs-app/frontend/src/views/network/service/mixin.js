/**
 * Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 * Copyright (C) 2017-2019 THL A29 Limited, a Tencent company. All rights reserved.
 * Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * http://opensource.org/licenses/MIT
 * Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
 * an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
 * specific language governing permissions and limitations under the License.
 */

import bkKeyer from '@open/components/keyer'
import mixinBase from '@open/mixins/network/mixin-base'
import { catchErrorHandler } from '@open/common/util'

export default {
    components: {
        bkKeyer
    },
    mixins: [mixinBase],
    data () {
        return {}
    },
    computed: {
        projectId () {
            return this.$route.params.projectId
        },
        searchScopeList () {
            const clusterList = this.$store.state.cluster.clusterList
            const results = clusterList.map(item => {
                return {
                    id: item.cluster_id,
                    name: item.name
                }
            })

            results.length && results.unshift({
                id: '',
                name: '全部集群'
            })

            return results
        },
        serviceList () {
            const list = this.$store.state.network.serviceList
            list.forEach(item => {
                item.isChecked = false
            })
            return JSON.parse(JSON.stringify(list))
        },
        selector () {
            if (this.curService && this.curService.data.spec.selector) {
                let results = ''
                const selector = Object.entries(this.curService.data.spec.selector)
                selector.forEach(item => {
                    const key = item[0]
                    const value = item[1]
                    results += key + '=' + value + '\n'
                })
                return results
            } else {
                return ''
            }
        },
        labelList () {
            if (this.curService && this.curService.data.metadata.labels) {
                const labels = Object.entries(this.curService.data.metadata.labels)
                return labels
            } else {
                return []
            }
        },
        endpoints () {
            return this.$store.state.network.endpoints
        },
        curLabelList () {
            const list = []
            const labels = this.curServiceDetail.config.metadata.labels
            // 如果有缓存直接使用
            if (this.curServiceDetail.config.webCache && this.curServiceDetail.config.webCache.labelListCache) {
                return this.curServiceDetail.config.webCache.labelListCache
            }
            for (const [key, value] of Object.entries(labels)) {
                list.push({
                    key: key,
                    value: value
                })
            }
            if (!list.length) {
                list.push({
                    key: '',
                    value: ''
                })
            }
            return list
        }
    },
    watch: {
        curServiceDetail () {
            const metadata = this.curServiceDetail.config.metadata
            if (metadata.lb_labels && metadata.lb_labels.BCSBALANCE) {
                this.algorithmIndex = metadata.lb_labels.BCSBALANCE
            } else {
                this.algorithmIndex = -1
            }
        },
        curPageData () {
            this.curPageData.forEach(item => {
                if (item.status === 'updating') {
                    this.getServiceStatus(item)
                }
            })
        }
    },
    methods: {
        /**
         * 刷新列表
         */
        refresh () {
            this.pageConf.curPage = 1
            this.isPageLoading = true
            this.getServiceList()
        },

        /**
         * 分页大小更改
         *
         * @param {number} pageSize pageSize
         */
        changePageSize (pageSize) {
            this.pageConf.pageSize = pageSize
            this.pageConf.curPage = 1
            this.initPageConf()
            this.pageChangeHandler()
        },

        /**
         * 切换页面时，清空轮询请求
         */
        leaveCallback () {
            for (const key of Object.keys(this.statusTimer)) {
                clearInterval(this.statusTimer[key])
            }
        },

        /**
         * 获取service的状态
         * @param  {object} service service
         * @param  {number} index   service索引
         */
        getServiceStatus (service, index) {
            const projectId = this.projectId
            const name = service.resourceName
            const namespace = service.namespace

            if (this.statusTimer[service._id]) {
                clearInterval(this.statusTimer[service._id])
            } else {
                this.statusTimer[service._id] = 0
            }

            // 对单个service的状态进行不断2秒间隔的查询
            this.statusTimer[service._id] = setInterval(async () => {
                try {
                    const res = await this.$store.dispatch('network/getServiceStatus', {
                        projectId,
                        namespace,
                        name
                    })
                    const data = res.data.data[0]

                    if (data.status !== 'updating') {
                        service.status = data.status
                        service.can_update = data.can_update
                        service.can_delete = data.can_delete
                        service.can_update_msg = data.can_update_msg
                        service.can_delete_msg = data.can_delete_msg
                        clearInterval(this.statusTimer[service._id])
                    }
                } catch (e) {
                    catchErrorHandler(e, this)
                }
            }, 2000)
        },

        /**
         * 确认删除service
         * @param  {object} service service
         */
        async removeService (service) {
            const self = this
            if (!service.permissions.use) {
                const params = {
                    project_id: this.projectId,
                    policy_code: 'use',
                    resource_code: service.namespace_id,
                    resource_name: service.namespace,
                    resource_type: 'namespace'
                }
                await this.$store.dispatch('getResourcePermissions', params)
            }

            this.$bkInfo({
                title: ``,
                clsName: 'biz-remove-dialog',
                content: this.$createElement('p', {
                    class: 'biz-confirm-desc'
                }, `确定要删除Service【${service.resourceName}】？`),
                async confirmFn () {
                    self.deleteService(service)
                }
            })
        },

        /**
         * 删除service
         * @param  {object} service service
         */
        async deleteService (service) {
            const projectId = this.projectId
            const namespace = service.namespace
            const clusterId = service.clusterId
            const serviceId = service.resourceName
            this.isPageLoading = true
            try {
                await this.$store.dispatch('network/deleteService', {
                    projectId,
                    clusterId,
                    namespace,
                    serviceId
                })

                this.$bkMessage({
                    theme: 'success',
                    message: '删除成功！'
                })
                this.initPageConf()
                this.getServiceList()
            } catch (e) {
                catchErrorHandler(e, this)
                this.isPageLoading = false
            }
        }
    }
}
