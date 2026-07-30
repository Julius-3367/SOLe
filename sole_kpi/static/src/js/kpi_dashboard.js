/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";

const UNIT_LABELS = { currency: "KES", percentage: "%", count: "", hours: "hrs" };
const STATUS_LABELS = { green: "Green", amber: "Amber", red: "Red", black: "Black", grey: "No Data" };

// SVG ring circumference: 2π × r=18
const CIRC = 2 * Math.PI * 18;

function pctToStatus(pct) {
    if (pct >= 90) return "green";
    if (pct >= 75) return "amber";
    if (pct >= 60) return "red";
    return "black";
}

function fmtNum(val, unit) {
    if (unit === "currency") {
        if (val >= 1_000_000) return (val / 1_000_000).toFixed(1) + "M";
        if (val >= 1_000) return (val / 1_000).toFixed(0) + "K";
        return val.toFixed(0);
    }
    if (unit === "percentage") return val.toFixed(1);
    return val % 1 === 0 ? val.toFixed(0) : val.toFixed(1);
}

export class KpiDashboard extends Component {
    static template = "sole_kpi.KpiDashboard";

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            periods: [],
            currentPeriodId: null,
            categories: [],
            counts: { green: 0, amber: 0, red: 0, black: 0, grey: 0 },
            overallPct: 0,
            overallStatus: "grey",
            overallDash: "0 " + CIRC,
            loading: true,
        });

        onWillStart(() => this._loadPeriods());
    }

    async _loadPeriods() {
        this.state.loading = true;
        try {
            const periods = await this.orm.searchRead(
                "sole.kpi.period", [],
                ["id", "name", "state"],
                { order: "date_start desc", limit: 24 }
            );
            this.state.periods = periods;
            if (periods.length) {
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
            this._updateSummary([]);
            return;
        }
        this.state.loading = true;
        try {
            const userId = session.uid;
            const entries = await this.orm.searchRead(
                "sole.kpi.entry",
                [["period_id", "=", this.state.currentPeriodId], ["user_id", "=", userId]],
                ["id", "indicator_id", "actual", "target", "achievement_pct", "status", "unit"],
                { order: "indicator_id" }
            );

            if (!entries.length) {
                this.state.categories = [];
                this._updateSummary([]);
                return;
            }

            const indIds = [...new Set(entries.map((e) => e.indicator_id[0]))];
            const indicators = await this.orm.searchRead(
                "sole.kpi.indicator",
                [["id", "in", indIds]],
                ["id", "name", "category_id", "target_display"]
            );
            const indMap = Object.fromEntries(indicators.map((i) => [i.id, i]));

            const catIds = [...new Set(indicators.map((i) => i.category_id[0]).filter(Boolean))];
            const cats = catIds.length
                ? await this.orm.searchRead(
                      "sole.kpi.category", [["id", "in", catIds]], ["id", "color_hex"]
                  )
                : [];
            const catHex = Object.fromEntries(cats.map((c) => [c.id, c.color_hex || "#e4e3e3"]));

            const catMap = {};
            for (const e of entries) {
                const ind = indMap[e.indicator_id[0]];
                if (!ind) continue;
                const catId = ind.category_id[0];
                const catName = ind.category_id[1];
                if (!catMap[catId]) {
                    catMap[catId] = { id: catId, name: catName, color: catHex[catId] || "#e4e3e3", entries: [] };
                }
                const status = e.status || "grey";
                const unit = e.unit || "count";
                catMap[catId].entries.push({
                    id: e.id,
                    indicator_name: ind.name,
                    target_display: ind.target_display || fmtNum(e.target, unit),
                    actual_display: fmtNum(e.actual, unit),
                    achievement_pct: e.achievement_pct || 0,
                    status,
                    status_label: STATUS_LABELS[status] || "No Data",
                    unit,
                    unit_label: UNIT_LABELS[unit] || "",
                });
            }

            this.state.categories = Object.values(catMap).sort((a, b) => a.name.localeCompare(b.name));
            this._updateSummary(entries.map((e) => ({ status: e.status || "grey", achievement_pct: e.achievement_pct || 0 })));
        } finally {
            this.state.loading = false;
        }
    }

    _updateSummary(entries) {
        const counts = { green: 0, amber: 0, red: 0, black: 0, grey: 0 };
        let total = 0, scorable = 0;
        for (const e of entries) {
            counts[e.status] = (counts[e.status] || 0) + 1;
            if (e.status !== "grey") { total += e.achievement_pct; scorable++; }
        }
        const overall = scorable > 0 ? Math.round(total / scorable) : 0;
        const capped = Math.min(overall, 100);
        this.state.counts = counts;
        this.state.overallPct = overall;
        this.state.overallStatus = scorable > 0 ? pctToStatus(overall) : "grey";
        this.state.overallDash = (capped / 100) * CIRC + " " + CIRC;
    }

    async onPeriodChange(ev) {
        const val = ev.target.value;
        this.state.currentPeriodId = val ? parseInt(val, 10) : null;
        await this._loadEntries();
    }
}

registry.category("actions").add("sole_kpi_dashboard", KpiDashboard);
