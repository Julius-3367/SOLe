/** @odoo-module **/

import { url } from '@web/core/utils/urls';
import { useService } from '@web/core/utils/hooks';
import { user } from '@web/core/user';

import { Component, onWillUnmount } from '@odoo/owl';

export class AppsBar extends Component {
	static template = 'muk_web_appsbar.AppsBar';
    static props = {};
	setup() {
        this.appMenuService = useService('app_menu');
        const currentCompany = user.activeCompany;
        if (currentCompany && currentCompany.has_appsbar_image) {
            this.sidebarImageUrl = url('/web/image', {
                model: 'res.company',
                field: 'appbar_image',
                id: currentCompany.id,
            });
        }
    }
}
