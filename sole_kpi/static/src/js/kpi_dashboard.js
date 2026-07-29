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
    green: "Green",
    amber: "Amber",
    red: "Red",
    black: "Black",
    grey: "No Data",
};

function formatNumber(val, unit) {
    if (unit === "currency") {
        if (val >= 1_000_000) return (val / 1_000_000).toFixed(1) + "M";
        if (val >= 1_000) return (val / 1_000).toFixed(0) + "K";
        return val.toFixed(0);
    }
    if (unit === "percentage") return val.toFixed(1);
    return val % 1 === 0 ? val.toFixed(0) : val.toFixed(1);
}

// SVG ring: circumference of r=18 circle = 2π×18 ≈ 113.1
const CIRC = 2 * Math.PI * 18;

function pctToStatus(pct) {
    if (pct >= 80) return "green";
    if (pct >= 70) return "amber";
    if (pct >= 60) return "red";
    return "black";
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
            const userId = this.env.uid;
            const entries = await this.orm.searchRead(
                "sole.kpi.entry",
                [
                    ["period_id", "=", this.state.currentPeriodId],
                    ["user_id", "=", userId],
                ],
                ["id", "indicator_id", "actual", "target", "achievement_pct", "status", "unit"],
                { order: "indicator_id" }
            );

            if (!entries.length) {
                this.state.categories = [];
                this._updateSummary([]);
                return;
            }

            const indicatorIds = [...new Set(entries.map((e) => e.indicator_id[0]))];
            const indicators = await this.orm.searchRead(
                "sole.kpi.indicator",
                [["id", "in", indicatorIds]],
                ["id", "name", "category_id", "target_display"]
            );

            const indicatorMap = {};
            for (const ind of indicators) indicatorMap[ind.id] = ind;

            // Fetch category colors
            const catIds = [...new Set(indicators.map((i) => i.category_id[0]).filter(Boolean))];
            const cats = catIds.length
                ? await this.orm.searchRead(
                      "sole.kpi.category",
                      [["id", "in", catIds]],
                      ["id", "color"]
                  )
                : [];
            const catColorMap = {};
            for (const c of cats) catColorMap[c.id] = c.color;

            const categoryMap = {};
            for (const entry of entries) {
                const ind = indicatorMap[entry.indicator_id[0]];
                if (!ind) continue;
                const catId = ind.category_id[0];
                const catName = ind.category_id[1];
                if (!categoryMap[catId]) {
                    categoryMap[catId] = {
                        id: catId,
                        name: catName,
                        color: catColorMap[catId] || null,
                        entries: [],
                    };
                }
                const status = entry.status || "grey";
                const unit = entry.unit || "count";
                categoryMap[catId].entries.push({
                    id: entry.id,
                    indicator_name: ind.name,
                    target: entry.target,
                    target_display: formatNumber(entry.target, unit),
                    actual_display: formatNumber(entry.actual, unit),
                    actual: entry.actual,
                    achievement_pct: entry.achievement_pct || 0,
                    status,
                    status_label: STATUS_LABELS[status] || "No Data",
                    unit,
                    unit_label: UNIT_LABELS[unit] || "",
                });
            }

            const allEntries = entries.map((e) => ({
                status: e.status || "grey",
                achievement_pct: e.achievement_pct || 0,
            }));

            this.state.categories = Object.values(categoryMap).sort((a, b) =>
                a.name.localeCompare(b.name)
            );
            this._updateSummary(allEntries);
        } finally {
            this.state.loading = false;
        }
    }

    _updateSummary(entries) {
        const counts = { green: 0, amber: 0, red: 0, black: 0, grey: 0 };
        let totalPct = 0;
        let scorable = 0;
        for (const e of entries) {
            counts[e.status] = (counts[e.status] || 0) + 1;
            if (e.status !== "grey") {
                totalPct += e.achievement_pct;
                scorable++;
            }
        }
        const overall = scorable > 0 ? Math.round(totalPct / scorable) : 0;
        const capped = Math.min(overall, 100);
        const dash = (capped / 100) * CIRC;
        this.state.counts = counts;
        this.state.overallPct = overall;
        this.state.overallStatus = scorable > 0 ? pctToStatus(overall) : "grey";
        this.state.overallDash = dash + " " + CIRC;
    }

    async onPeriodChange(ev) {
        const val = ev.target.value;
        this.state.currentPeriodId = val ? parseInt(val, 10) : null;
        await this._loadEntries();
    }
}

registry.category("actions").add("sole_kpi_dashboard", KpiDashboard);
