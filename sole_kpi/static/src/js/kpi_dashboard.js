/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const UNIT_LABELS = {
    currency: "KES",
    percentage: "%",
    count: "",
    hours: "hrs",
};

const STATUS_LABELS = {
    green: "Green ✓",
    amber: "Amber",
    red: "Red",
    black: "Black ✗",
    grey: "No Data",
};

export class KpiDashboard extends Component {
    static template = "sole_kpi.KpiDashboard";

    setup() {
        this.orm = useService("orm");
        this.user = useService("user");
        this.state = useState({
            periods: [],
            currentPeriodId: null,
            categories: [],
            loading: true,
        });

        onWillStart(async () => {
            await this._loadPeriods();
        });
    }

    async _loadPeriods() {
        this.state.loading = true;
        try {
            const periods = await this.orm.searchRead(
                "sole.kpi.period",
                [],
                ["id", "name", "state"],
                { order: "date_start desc", limit: 24 }
            );
            this.state.periods = periods;
            if (periods.length > 0) {
                this.state.currentPeriodId = periods[0].id;
                await this._loadEntries();
            }
        } finally {
            this.state.loading = false;
        }
    }

    async _loadEntries() {
        if (!this.state.currentPeriodId) {
            this.state.categories = [];
            return;
        }
        this.state.loading = true;
        try {
            const userId = this.user.userId;
            const entries = await this.orm.searchRead(
                "sole.kpi.entry",
                [
                    ["period_id", "=", this.state.currentPeriodId],
                    ["user_id", "=", userId],
                ],
                [
                    "id",
                    "indicator_id",
                    "actual",
                    "target",
                    "achievement_pct",
                    "status",
                    "unit",
                ],
                { order: "indicator_id" }
            );

            if (!entries.length) {
                this.state.categories = [];
                return;
            }

            const indicatorIds = [...new Set(entries.map((e) => e.indicator_id[0]))];
            const indicators = await this.orm.searchRead(
                "sole.kpi.indicator",
                [["id", "in", indicatorIds]],
                ["id", "name", "category_id", "target_display"]
            );

            const indicatorMap = {};
            for (const ind of indicators) {
                indicatorMap[ind.id] = ind;
            }

            const categoryMap = {};
            for (const entry of entries) {
                const ind = indicatorMap[entry.indicator_id[0]];
                if (!ind) continue;
                const catId = ind.category_id[0];
                const catName = ind.category_id[1];
                if (!categoryMap[catId]) {
                    categoryMap[catId] = { id: catId, name: catName, entries: [] };
                }
                categoryMap[catId].entries.push({
                    id: entry.id,
                    indicator_name: ind.name,
                    target: entry.target,
                    target_display: ind.target_display || null,
                    actual: entry.actual,
                    achievement_pct: entry.achievement_pct || 0,
                    status: entry.status || "grey",
                    status_label: STATUS_LABELS[entry.status] || "No Data",
                    unit: entry.unit,
                    unit_label: UNIT_LABELS[entry.unit] || "",
                });
            }

            this.state.categories = Object.values(categoryMap).sort((a, b) =>
                a.name.localeCompare(b.name)
            );
        } finally {
            this.state.loading = false;
        }
    }

    async onPeriodChange(ev) {
        const val = ev.target.value;
        this.state.currentPeriodId = val ? parseInt(val, 10) : null;
        await this._loadEntries();
    }
}

registry.category("actions").add("sole_kpi_dashboard", KpiDashboard);
