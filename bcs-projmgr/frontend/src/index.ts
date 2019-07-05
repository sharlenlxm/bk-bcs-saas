/*
 * Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 * Copyright (C) 2017-2019 THL A29 Limited, a Tencent company. All rights reserved.
 * Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 * http://opensource.org/licenses/MIT
 * Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
 * an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
 * specific language governing permissions and limitations under the License.
 *
 */

/// <reference path='./typings/index.d.ts' />

declare module 'vue/types/vue' {
    interface Vue {
        $bkMessage: any
        $bkInfo: any
        $showAskPermissionDialog: any
        iframeUtil: any
    }
}
import 'core-js/es7/array'
import Vue from 'vue'
import createRouter from './router'
import store from './store'
import eventBus from './utils/eventBus'
import App from './views/App.vue'
import Logo from './components/Logo/index.vue'
import EmptyTips from './components/EmptyTips/index.vue'
import ShowTooltip from './components/ShowTooltip/index.vue'
import iframeUtil from './utils/iframeUtil'

import VeeValidate from 'vee-validate'
import ExtendsCustomRules from './utils/customRules'
import validDictionary from './utils/validDictionary'
import showAskPermissionDialog from './components/AskPermissionDialog'

import { judgementLsVersion } from './utils/util'

import './assets/scss/index'

// @ts-ignore
Vue.use(VeeValidate, {
    fieldsBagName: 'veeFields',
    locale: 'cn'
})

VeeValidate.Validator.localize(validDictionary)
ExtendsCustomRules(VeeValidate.Validator.extend)

Vue.component('Logo', Logo)
Vue.component('EmptyTips', EmptyTips)
Vue.component('ShowTooltip', ShowTooltip)

const router = createRouter(store)
window.eventBus = eventBus
Vue.prototype.iframeUtil = iframeUtil(router)
Vue.prototype.$showAskPermissionDialog = showAskPermissionDialog

// 判断localStorage版本, 旧版本需要清空
judgementLsVersion()

window.devops = new Vue({
    el: "#devops-root",
    router,
    store,
    render (h) {
        return h(App)
    }
})
