/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const CIRC = 2 * Math.PI * 18;
const STATUS_LABELS = { green: "Green", amber: "Amber", red: "Red", black: "Black", grey: "No Data" };
const UNIT_LABELS = { currency: "KES", percentage: "%", count: "", hours: "hrs" };

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
    return val % 1 === 0 ? String(val | 0) : val.toFixed(1);
}

function buildSummary(entries) {
    const counts = { green: 0, amber: 0, red: 0, black: 0, grey: 0 };
    let total = 0, scorable = 0;
    for (const e of entries) {
        counts[e.status] = (counts[e.status] || 0) + 1;
        if (e.status !== "grey") { total += e.achievement_pct; scorable++; }
    }
    const pct = scorable > 0 ? Math.round(total / scorable) : 0;
    return {
        counts,
        overallPct: pct,
        overallStatus: scorable > 0 ? pctToStatus(pct) : "grey",
        overallDash: (Math.min(pct, 100) / 100) * CIRC + " " + CIRC,
    };
}

export class KpiCompanyScorecard extends Component {
    static template = "sole_kpi.KpiCompanyScorecard";

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            periods: [],
            currentPeriodId: null,
            selectedRoleId: null,
            roles: [],
            staffRows: [],      // [{user, role, summary, categories}]
            companySummary: null,
            loading: true,
            expandedUser: null, // userId of expanded row
        });

        onWillStart(() => this._init());
    }

    async _init() {
        this.state.loading = true;
        try {
            const [periods, roles] = await Promise.all([
                this.orm.searchRead("sole.kpi.period", [], ["id", "name", "state"], { order: "date_start desc, id desc", limit: 24 }),
                this.orm.searchRead("sole.kpi.role", [["active", "=", true]], ["id", "name", "code"]),
            ]);
            this.state.periods = periods;
            this.state.roles = roles;
            if (periods.length) {
                this.state.currentPeriodId = periods[0].id;
                await this._loadScorecard();
            }
        } finally {
            this.state.loading = false;
        }
    }

    async _loadScorecard() {
        if (!this.state.currentPeriodId) {
            this.state.staffRows = [];
            this.state.companySummary = null;
            return;
        }
        this.state.loading = true;
        try {
            const domain = [["period_id", "=", this.state.currentPeriodId]];
            if (this.state.selectedRoleId) {
                domain.push(["role_id", "=", this.state.selectedRoleId]);
            }

            const entries = await this.orm.searchRead(
                "sole.kpi.entry",
                domain,
                ["id", "user_id", "role_id", "indicator_id", "actual", "target",
                 "achievement_pct", "status", "unit", "category_id"],
                { order: "user_id, indicator_id" }
            );

            if (!entries.length) {
                this.state.staffRows = [];
                this.state.companySummary = null;
                return;
            }

            // Fetch category hex colors
            const catIds = [...new Set(entries.map((e) => e.category_id[0]).filter(Boolean))];
            const cats = catIds.length
                ? await this.orm.searchRead("sole.kpi.category", [["id", "in", catIds]], ["id", "color_hex"])
                : [];
            const catHex = Object.fromEntries(cats.map((c) => [c.id, c.color_hex || "#e4e3e3"]));

            // Fetch indicator names
            const indIds = [...new Set(entries.map((e) => e.indicator_id[0]))];
            const inds = await this.orm.searchRead(
                "sole.kpi.indicator", [["id", "in", indIds]], ["id", "name", "target_display"]
            );
            const indMap = Object.fromEntries(inds.map((i) => [i.id, i]));

            // Group by user
            const userMap = {};
            for (const e of entries) {
                const uid = e.user_id[0];
                if (!userMap[uid]) {
                    userMap[uid] = {
                        user: { id: uid, name: e.user_id[1] },
                        role: e.role_id ? { id: e.role_id[0], name: e.role_id[1] } : null,
                        entries: [],
                        catMap: {},
                    };
                }
                userMap[uid].entries.push(e);
                const catId = e.category_id[0];
                const catName = e.category_id[1];
                if (catId && !userMap[uid].catMap[catId]) {
                    userMap[uid].catMap[catId] = { id: catId, name: catName, color: catHex[catId] || "#e4e3e3", entries: [] };
                }
                if (catId) {
                    const ind = indMap[e.indicator_id[0]];
                    const unit = e.unit || "count";
                    userMap[uid].catMap[catId].entries.push({
                        id: e.id,
                        indicator_name: ind ? ind.name : e.indicator_id[1],
                        target_display: (ind && ind.target_display) || fmtNum(e.target, unit),
                        actual_display: fmtNum(e.actual, unit),
                        achievement_pct: e.achievement_pct || 0,
                        status: e.status || "grey",
                        status_label: STATUS_LABELS[e.status] || "No Data",
                        unit_label: UNIT_LABELS[unit] || "",
                    });
                }
            }

            const staffRows = Object.values(userMap).map((row) => ({
                user: row.user,
                role: row.role,
                summary: buildSummary(row.entries.map((e) => ({ status: e.status || "grey", achievement_pct: e.achievement_pct || 0 }))),
                categories: Object.values(row.catMap).sort((a, b) => a.name.localeCompare(b.name)),
            }));

            // Sort: by overall score desc
            staffRows.sort((a, b) => b.summary.overallPct - a.summary.overallPct);

            this.state.staffRows = staffRows;
            this.state.companySummary = buildSummary(
                entries.map((e) => ({ status: e.status || "grey", achievement_pct: e.achievement_pct || 0 }))
            );
        } finally {
            this.state.loading = false;
        }
    }

    async onPeriodChange(ev) {
        this.state.currentPeriodId = ev.target.value ? parseInt(ev.target.value, 10) : null;
        this.state.expandedUser = null;
        await this._loadScorecard();
    }

    async onRoleChange(ev) {
        this.state.selectedRoleId = ev.target.value ? parseInt(ev.target.value, 10) : null;
        this.state.expandedUser = null;
        await this._loadScorecard();
    }

    toggleExpand(userId) {
        this.state.expandedUser = this.state.expandedUser === userId ? null : userId;
    }
}

registry.category("actions").add("sole_kpi_company_scorecard", KpiCompanyScorecard);
