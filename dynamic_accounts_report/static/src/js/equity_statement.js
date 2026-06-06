/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState } from "@odoo/owl";
import { BlockUI } from "@web/core/ui/block_ui";
import { download } from "@web/core/network/download";
const actionRegistry = registry.category("actions");

class EquityStatement extends Component {
    async setup() {
        super.setup(...arguments);
        this.initial_render = true;
        this.orm = useService('orm');
        this.action = useService('action');
        this.state = useState({
            data: null,
            filter_data: null,
            title: null,
        });
        this.wizard_id = await this.orm.call(
            "equity.statement.report", "create", [{}]) | null;
        this.load_data(self.initial_render = true);
    }

    async load_data() {
        var self = this;
        var action_title = self.props.action.display_name;
        try {
            let result = await self.orm.call(
                "equity.statement.report", "view_report",
                [this.wizard_id]);
            self.state.data = result[0];
            self.state.filter_data = result[1];
            self.state.title = action_title;
        } catch (el) {
            window.location.href;
        }
    }

    async print_pdf(ev) {
        ev.preventDefault();
        var self = this;
        let result = await self.orm.call(
            "equity.statement.report", "view_report",
            [this.wizard_id]);
        self.state.data = result[0];
        return self.action.doAction({
            'type': 'ir.actions.report',
            'report_type': 'qweb-pdf',
            'report_name': 'dynamic_accounts_report.equity_statement_pdf',
            'report_file': 'dynamic_accounts_report.equity_statement_pdf',
            'data': {
                'data': self.state,
                'report_name': self.props.action.display_name,
            },
            'display_name': self.props.action.display_name,
        });
    }

    async print_xlsx(ev) {
        var self = this;
        let result = await self.orm.call(
            "equity.statement.report", "view_report",
            [this.wizard_id]);
        self.state.data = result[0];
        var action = {
            'data': {
                'model': 'equity.statement.report',
                'data': JSON.stringify(self.state.data),
                'output_format': 'xlsx',
                'report_name': self.props.action.display_name,
            },
        };
        BlockUI;
        await download({
            url: '/xlsx_report',
            data: action.data,
            complete: () => unblockUI,
            error: (error) => self.call('crash_manager', 'rpc_error', error),
        });
    }

    async apply_journal(ev) {
        var self = this;
        var jid = ev.currentTarget.querySelector('span.d-none').textContent.trim();
        this.filter = { 'journal_ids': jid };
        await self.orm.call(
            "equity.statement.report", "filter",
            [this.wizard_id, this.filter]);
        self.initial_render = false;
        self.load_data(self.initial_render);
    }

    async apply_entries(ev) {
        var self = this;
        this.filter = { 'target': ev.target.value };
        await self.orm.call(
            "equity.statement.report", "filter",
            [this.wizard_id, this.filter]);
        self.initial_render = false;
        self.load_data(self.initial_render);
    }

    async apply_date(ev) {
        var self = this;
        if (ev.target.name === 'start_date') {
            this.filter = { ...this.filter, date_from: ev.target.value };
        } else if (ev.target.name === 'end_date') {
            this.filter = { ...this.filter, date_to: ev.target.value };
        } else {
            this.filter = ev.target.attributes["data-value"].value;
        }
        await self.orm.call(
            "equity.statement.report", "filter",
            [this.wizard_id, this.filter]);
        self.initial_render = false;
        self.load_data(self.initial_render);
    }
}

EquityStatement.template = 'eqs_template_new';
actionRegistry.add("eqs", EquityStatement);
