/** @odoo-module **/

/**
 * The purpose of this widget is to show a toggle button on depreciation and
 * installment lines for posted/un-posted lines. When clicked, it calls the
 * method create_move on the object account.asset.depreciation.line.
 * Note that this widget can only work on the account.asset.depreciation.line
 * model as some of its fields are hardcoded.
 */

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";

export class AccountAssetDeprecToggler extends Component {
    static template = "base_accounting_kit.DeprecLinesToggler";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
    }

    get buttonClass() {
        let extra = "";
        if (this.props.record.data.move_posted_check) {
            extra = "o_is_posted";
        } else if (this.props.record.data.move_check) {
            extra = "o_unposted";
        }
        return `btn btn-sm btn-link fa fa-circle o_deprec_lines_toggler ${extra}`;
    }

    get title() {
        if (this.props.record.data.move_posted_check) {
            return "Posted";
        } else if (this.props.record.data.move_check) {
            return "Accounting entries waiting for manual verification";
        }
        return "Unposted";
    }

    get isDisabled() {
        return Boolean(
            this.props.record.data.move_posted_check ||
            this.props.record.data.move_check
        );
    }

    async onClick(event) {
        event.stopPropagation();
        await this.orm.call(
            "account.asset.depreciation.line",
            "create_move",
            [this.props.record.resId]
        );
        await this.props.record.model.root.load();
    }
}

registry.category("fields").add("deprec_lines_toggler", { component: AccountAssetDeprecToggler, supportedTypes: ["boolean"] });
