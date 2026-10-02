import "../lib/agGrid";

import {
  Button, Group, Pagination, Paper, Select, Text, TextInput, Tooltip,
  useComputedColorScheme,
} from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { IconDownload, IconSearch, IconUserOff, IconUsers, IconX } from "@tabler/icons-react";
import type { ColDef, GetRowIdParams, RowClassRules, SortChangedEvent } from "ag-grid-community";
import { AgGridReact, type CustomCellRendererProps } from "ag-grid-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
  type CustomerListParams, type CustomerSort, customersExportUrl, useCustomers, useFilterOptions,
  useKpis,
} from "../api/queries";
import type { GlobalFilters } from "../api/types";
import { RiskBadge } from "../components/Badges";
import { FilterMenu } from "../components/FilterMenu";
import { PageHeader } from "../components/PageHeader";
import { EmptyState, ErrorState } from "../components/States";
import { formatMoney, formatNumber, formatShare } from "../lib/format";
import { useCustomerNav } from "../store/customerNav";
import { useFiltersStore, useGlobalFilters } from "../store/filters";
import { agGridThemes } from "../theme/agGridTheme";
import classes from "./CustomersPage.module.css";

type Row = NonNullable<ReturnType<typeof useCustomers>["data"]>["items"][number];

const PAGE_SIZES = ["25", "50", "100"];
const SORTABLE: Record<string, CustomerSort> = {
  customer_id: "customer_id",
  p_real: "p_real",
  monthly_bill: "monthly_bill",
  revenue_at_risk_monthly: "revenue_at_risk_monthly",
};
const ACTIVE_LEVELS = ["High", "Medium", "Low"];

/**
 * Filtres effectifs de la liste : sans filtre de niveau, les inactifs sont exclus (ce sont des
 * clients à vérifier ou reconquérir, pas à fidéliser) ; « Voir les inactifs » les affiche.
 */
function effectiveFilters(filters: GlobalFilters): GlobalFilters {
  return filters.risk_level.length ? filters : { ...filters, risk_level: ACTIVE_LEVELS };
}

function RiskBarCell({ data }: CustomCellRendererProps<Row>) {
  if (!data) return null;
  const key = data.risk_level.toLowerCase();
  const width = Math.min(100, (100 * data.p_real) / 0.2);
  return (
    <div className={classes.riskCell}>
      <span className={classes.riskValue}>{formatShare(data.p_real, 1)}</span>
      <span className={classes.riskTrack} aria-hidden>
        <span className={classes.riskFill} style={{ width: `${String(width)}%`, background: `var(--risk-${key})` }} />
      </span>
    </div>
  );
}

function LevelCell({ data }: CustomCellRendererProps<Row>) {
  return data ? <RiskBadge level={data.risk_level} /> : null;
}

function ReasonCell({ data }: CustomCellRendererProps<Row>) {
  if (!data) return null;
  return <span className={classes.ellipsis} title={data.top_reason ?? ""}>{data.top_reason ?? "—"}</span>;
}

function ActionCell({ data }: CustomCellRendererProps<Row>) {
  if (!data) return null;
  return <span className={classes.action} data-inactive={data.inactive || undefined} title={data.action}>{data.action}</span>;
}

function readParams(params: URLSearchParams): CustomerListParams {
  const size = Number(params.get("size") ?? 25);
  const sort = params.get("sort") as CustomerSort | null;
  return {
    page: Math.max(1, Number(params.get("page") ?? 1) || 1),
    size: PAGE_SIZES.includes(String(size)) ? size : 25,
    sort: sort && Object.values(SORTABLE).includes(sort) ? sort : "p_real",
    order: params.get("order") === "asc" ? "asc" : "desc",
    search: params.get("q") ?? "",
  };
}

export function CustomersPage() {
  const scheme = useComputedColorScheme("light");
  const [params, setParams] = useSearchParams();
  const list = readParams(params);
  const openId = params.get("client") ? Number(params.get("client")) : null;
  const filters = useGlobalFilters();
  const setFilter = useFiltersStore((s) => s.set);
  const effective = useMemo(() => effectiveFilters(filters), [filters]);
  const showingInactive = filters.risk_level.length === 1 && filters.risk_level[0] === "Inactif";

  // Recherche : saisie fluide, requête après 250 ms.
  const [searchInput, setSearchInput] = useState(list.search);
  const [search] = useDebouncedValue(searchInput, 250);

  const update = useCallback(
    (patch: Record<string, string | null>) => {
      const next = new URLSearchParams(window.location.search);
      for (const [k, v] of Object.entries(patch)) {
        if (v === null || v === "") next.delete(k);
        else next.set(k, v);
      }
      setParams(next, { replace: patch.client === undefined });
    },
    [setParams],
  );

  useEffect(() => {
    if (search !== list.search) update({ q: search || null, page: null });
  }, [search, list.search, update]);

  const query = useCustomers(list, effective);
  const kpis = useKpis(effective);
  const options = useFilterOptions();
  const data = query.data;
  const rows = useMemo(() => data?.items ?? [], [data]);

  // Navigation dans la fiche : précédent / suivant dans la liste filtrée, y compris d'une page à l'autre.
  const pendingSelect = useRef<"first" | "last" | null>(null);
  useEffect(() => {
    if (!pendingSelect.current || query.isFetching || rows.length === 0) return;
    const target = pendingSelect.current === "first" ? rows[0] : rows[rows.length - 1];
    pendingSelect.current = null;
    if (target) update({ client: String(target.customer_id) });
  }, [rows, query.isFetching, update]);

  const index = openId === null ? -1 : rows.findIndex((r) => r.customer_id === openId);
  const total = data?.total_n_rows ?? 0;
  const globalIndex = index >= 0 ? (list.page - 1) * list.size + index + 1 : null;
  const goPrev = index > 0 || list.page > 1
    ? () => {
        const prev = rows[index - 1];
        if (index > 0 && prev) update({ client: String(prev.customer_id) });
        else { pendingSelect.current = "last"; update({ page: String(list.page - 1) }); }
      }
    : null;
  const goNext = index >= 0 && (index < rows.length - 1 || list.page < (data?.total_pages ?? 1))
    ? () => {
        const next = rows[index + 1];
        if (next) update({ client: String(next.customer_id) });
        else { pendingSelect.current = "first"; update({ page: String(list.page + 1) }); }
      }
    : null;

  // La fiche (globale, dans le layout) navigue dans la liste filtrée de cette page.
  const setNav = useCustomerNav((st) => st.setNav);
  const clearNav = useCustomerNav((st) => st.clearNav);
  const position = globalIndex !== null ? `${formatNumber(globalIndex)} / ${formatNumber(total)}` : null;
  useEffect(() => {
    setNav({ onPrev: goPrev, onNext: goNext, position });
  });
  useEffect(() => clearNav, [clearNav]);

  const columnDefs = useMemo<ColDef<Row>[]>(() => {
    const sortState = (col: string) => (SORTABLE[col] === list.sort ? list.order : null);
    return [
      { colId: "customer_id", field: "customer_id", headerName: "Client", width: 104, sortable: true, sort: sortState("customer_id"), cellClass: classes.mono },
      { colId: "risk_level", field: "risk_level", headerName: "Niveau", width: 100, sortable: false, cellRenderer: LevelCell },
      { colId: "p_real", field: "p_real", headerName: "Risque / mois", width: 160, sortable: true, sort: sortState("p_real"), cellRenderer: RiskBarCell, headerTooltip: "Probabilité de départ sur un mois, au taux de churn réel supposé de 2 %" },
      { colId: "top_reason", field: "top_reason", headerName: "Raison principale (selon le modèle)", flex: 1.5, minWidth: 200, sortable: false, cellRenderer: ReasonCell },
      { colId: "action", field: "action", headerName: "Action suggérée", flex: 1, minWidth: 170, sortable: false, cellRenderer: ActionCell },
      { colId: "monthly_bill", field: "monthly_bill", headerName: "Facture / mois", width: 116, sortable: true, sort: sortState("monthly_bill"), type: "rightAligned", valueFormatter: (p) => formatMoney(p.value as number | null, 2), cellClass: classes.num },
      { colId: "revenue_at_risk_monthly", field: "revenue_at_risk_monthly", headerName: "En jeu / mois", width: 110, sortable: true, sort: sortState("revenue_at_risk_monthly"), type: "rightAligned", valueFormatter: (p) => formatMoney(p.value as number, 2), cellClass: classes.num, headerTooltip: "Risque mensuel × facture (taux supposé)" },
      { colId: "segment", field: "segment", headerName: "Profil", flex: 0.9, minWidth: 140, sortable: false, tooltipField: "segment" },
    ];
  }, [list.sort, list.order]);

  const onSortChanged = useCallback(
    (e: SortChangedEvent<Row>) => {
      const col = e.api.getColumnState().find((c) => c.sort);
      const field = col ? SORTABLE[col.colId] : undefined;
      if (!col || !field) {
        update({ sort: null, order: null, page: null });
        return;
      }
      if (field !== list.sort || col.sort !== list.order) {
        update({ sort: field === "p_real" ? null : field, order: col.sort === "desc" ? null : col.sort ?? null, page: null });
      }
    },
    [list.sort, list.order, update],
  );

  const rowClassRules = useMemo<RowClassRules<Row>>(
    () => ({ [classes.openRow ?? "open-row"]: (p) => p.data?.customer_id === openId }),
    [openId],
  );

  const equiv = kpis.data?.n_portfolio_equiv;
  const title = kpis.data
    ? showingInactive
      ? `${formatNumber(kpis.data.n_rows)} clients inactifs à vérifier ou reconquérir`
      : `${formatNumber(kpis.data.n_rows)} clients à fidéliser correspondent aux filtres`
    : "";
  const actionValues = options.data?.dimensions.find((d) => d.dimension === "action")?.values ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Clients à risque"
        title={title}
        loading={!kpis.data}
        description={
          kpis.data
            ? `Clients dans la base (lignes réelles), triés par risque. Équivalent portefeuille : ≈ ${formatNumber(equiv)} clients (estimation au taux supposé de 2 %/mois).${showingInactive ? "" : " Inactifs exclus : ils relèvent d'une vérification de ligne."}`
            : undefined
        }
      />
      <Paper withBorder className={classes.tablePaper}>
        <Group justify="space-between" gap="sm" p="md" wrap="wrap" className={classes.toolbar}>
          <Group gap="sm" wrap="wrap">
            <TextInput
              size="xs"
              w={220}
              placeholder="Rechercher un identifiant"
              leftSection={<IconSearch size={14} />}
              rightSection={searchInput ? (
                <IconX size={14} style={{ cursor: "pointer" }} onClick={() => { setSearchInput(""); }} aria-label="Effacer la recherche" />
              ) : null}
              value={searchInput}
              onChange={(e) => { setSearchInput(e.currentTarget.value.replace(/\D/g, "")); }}
              aria-label="Rechercher un client par identifiant"
              inputMode="numeric"
            />
            <FilterMenu dimension="action" values={actionValues} />
            <Button
              size="xs"
              variant={showingInactive ? "filled" : "default"}
              color={showingInactive ? "violet" : "gray"}
              leftSection={showingInactive ? <IconUsers size={14} /> : <IconUserOff size={14} />}
              onClick={() => { setFilter("risk_level", showingInactive ? [] : ["Inactif"]); update({ page: null }); }}
            >
              {showingInactive ? "Revenir aux clients actifs" : "Voir les inactifs"}
            </Button>
          </Group>
          <Group gap="sm">
            <Text size="xs" c="var(--app-text-muted)">
              {data ? `${formatNumber(total)} clients dans la base` : ""}
            </Text>
            <Tooltip label="Toute la sélection filtrée, triée comme la table (CSV pour Excel : « ; », virgule décimale)">
              <Button
                size="xs"
                variant="light"
                leftSection={<IconDownload size={14} />}
                component="a"
                href={customersExportUrl({ sort: list.sort, order: list.order, search: list.search }, effective)}
                download
                disabled={!total}
              >
                Exporter CSV
              </Button>
            </Tooltip>
          </Group>
        </Group>

        {query.error ? (
          <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
        ) : data && total === 0 ? (
          <EmptyState
            title="Aucun client ne correspond"
            description={list.search ? `Aucun identifiant ne contient « ${list.search} » avec ces filtres.` : "Élargissez les filtres pour afficher des clients."}
          />
        ) : (
          <div className={classes.grid} style={{ opacity: query.isFetching && !query.isLoading ? 0.7 : 1 }}>
            <AgGridReact<Row>
              theme={agGridThemes[scheme]}
              rowData={rows}
              columnDefs={columnDefs}
              getRowId={(p: GetRowIdParams<Row>) => String(p.data.customer_id)}
              domLayout="autoHeight"
              loading={query.isLoading}
              suppressCellFocus
              suppressMultiSort
              rowClassRules={rowClassRules}
              onSortChanged={onSortChanged}
              onRowClicked={(e) => { if (e.data) update({ client: String(e.data.customer_id) }); }}
              tooltipShowDelay={400}
              overlayLoadingTemplate='<span class="ag-overlay-loading-center">Chargement des clients…</span>'
              defaultColDef={{ resizable: true, suppressMovable: true, comparator: () => 0 }}
              rowStyle={{ cursor: "pointer" }}
            />
          </div>
        )}

        {data && total > 0 && (
          <Group justify="space-between" p="md" className={classes.footer}>
            <Text size="xs" c="var(--app-text-muted)" style={{ fontVariantNumeric: "tabular-nums" }}>
              {formatNumber((list.page - 1) * list.size + 1)}–{formatNumber(Math.min(list.page * list.size, total))} sur {formatNumber(total)}
            </Text>
            <Group gap="md">
              <Group gap={6}>
                <Text size="xs" c="var(--app-text-muted)">Par page</Text>
                <Select
                  size="xs"
                  w={76}
                  data={PAGE_SIZES}
                  value={String(list.size)}
                  onChange={(v) => { update({ size: v === "25" ? null : v, page: null }); }}
                  allowDeselect={false}
                  aria-label="Clients par page"
                />
              </Group>
              <Pagination
                size="sm"
                total={data.total_pages}
                value={list.page}
                onChange={(p) => { update({ page: p === 1 ? null : String(p) }); }}
                siblings={1}
                boundaries={1}
                getControlProps={(control) => ({ "aria-label": control === "next" ? "Page suivante" : control === "previous" ? "Page précédente" : control })}
              />
            </Group>
          </Group>
        )}
      </Paper>

    </>
  );
}
