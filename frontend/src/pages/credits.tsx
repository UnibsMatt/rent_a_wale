import { useState } from "react";
import { Coins, ReceiptText } from "lucide-react";
import { useBalance, usePricing, usePurchaseCredits, useTransactions } from "@/hooks/use-credits";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Pagination } from "@/components/pagination";
import { CardSkeleton, EmptyState, ErrorState, TableSkeleton } from "@/components/states";
import { formatCredits, formatDate, formatRate, formatRunway } from "@/lib/format";
import { cn } from "@/lib/utils";

const QUICK_AMOUNTS = [100, 500, 1000];

const KIND_STYLE: Record<string, string> = {
  purchase: "border-emerald-500/40 bg-emerald-500/15 text-emerald-500",
  usage: "border-blue-500/40 bg-blue-500/15 text-blue-400",
  adjustment: "border-amber-500/40 bg-amber-500/15 text-amber-500",
  refund: "border-purple-500/40 bg-purple-500/15 text-purple-400",
};

export function CreditsPage() {
  const balanceQuery = useBalance();
  const pricingQuery = usePricing();
  const purchaseMutation = usePurchaseCredits();
  const [amount, setAmount] = useState("100");
  const [page, setPage] = useState(1);
  const transactionsQuery = useTransactions(page);

  const parsedAmount = Number(amount);
  const amountValid = Number.isFinite(parsedAmount) && parsedAmount > 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Credits</h1>
        <p className="text-sm text-muted-foreground">
          Buy credits and review your billing history.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Balance */}
        {balanceQuery.isLoading ? (
          <CardSkeleton />
        ) : (
          <Card>
            <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Current balance
              </CardTitle>
              <Coins className="h-4 w-4 text-primary" aria-hidden />
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-semibold tabular-nums">
                {formatCredits(balanceQuery.data?.balance)}
              </p>
              <p className="mt-2 text-xs text-muted-foreground">
                Spending {formatCredits(balanceQuery.data?.estimated_hourly_spend)}/h · runway{" "}
                {formatRunway(balanceQuery.data?.runway_hours ?? null)}
              </p>
            </CardContent>
          </Card>
        )}

        {/* Purchase */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Buy credits</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="purchase-amount">Amount</Label>
              <Input
                id="purchase-amount"
                inputMode="numeric"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </div>
            <div className="flex gap-2">
              {QUICK_AMOUNTS.map((quick) => (
                <Button
                  key={quick}
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setAmount(String(quick))}
                >
                  {quick}
                </Button>
              ))}
            </div>
            <Button
              className="w-full"
              disabled={!amountValid}
              loading={purchaseMutation.isPending}
              onClick={() => purchaseMutation.mutate(parsedAmount)}
            >
              Purchase {amountValid ? formatCredits(parsedAmount) : ""} credits
            </Button>
          </CardContent>
        </Card>

        {/* Pricing */}
        {pricingQuery.isLoading ? (
          <CardSkeleton />
        ) : pricingQuery.data ? (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Current pricing{" "}
                <span className="text-xs font-normal text-muted-foreground">
                  ({pricingQuery.data.name})
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Base / hour</dt>
                  <dd className="tabular-nums">{formatRate(pricingQuery.data.base_cost_per_hour)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Per CPU core / hour</dt>
                  <dd className="tabular-nums">
                    {formatRate(pricingQuery.data.cpu_cost_per_core_hour)}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Per GB RAM / hour</dt>
                  <dd className="tabular-nums">
                    {formatRate(pricingQuery.data.memory_cost_per_gb_hour)}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Per GB storage / hour</dt>
                  <dd className="tabular-nums">
                    {formatRate(pricingQuery.data.storage_cost_per_gb_hour)}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">Per extra service / hour</dt>
                  <dd className="tabular-nums">
                    {formatRate(pricingQuery.data.service_cost_per_hour)}
                  </dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        ) : null}
      </div>

      {/* Transactions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Transactions</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {transactionsQuery.isLoading ? (
            <TableSkeleton rows={5} cols={4} />
          ) : transactionsQuery.isError ? (
            <ErrorState
              error={transactionsQuery.error}
              onRetry={() => transactionsQuery.refetch()}
              className="m-4"
            />
          ) : (transactionsQuery.data?.items ?? []).length === 0 ? (
            <EmptyState
              className="m-4"
              icon={<ReceiptText className="h-8 w-8" />}
              title="No transactions yet"
              description="Purchases and usage charges will appear here."
            />
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Type</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Balance after</TableHead>
                    <TableHead>Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {transactionsQuery.data?.items.map((tx) => {
                    const negative = Number(tx.amount) < 0;
                    return (
                      <TableRow key={tx.id}>
                        <TableCell>
                          <Badge className={KIND_STYLE[tx.kind] ?? ""}>{tx.kind}</Badge>
                        </TableCell>
                        <TableCell
                          className={cn(
                            "tabular-nums",
                            negative ? "text-red-400" : "text-emerald-500",
                          )}
                        >
                          {negative ? "" : "+"}
                          {formatCredits(tx.amount)}
                        </TableCell>
                        <TableCell className="tabular-nums">
                          {formatCredits(tx.balance_after)}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {formatDate(tx.created_at)}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
              <Pagination
                page={page}
                pageSize={transactionsQuery.data?.page_size ?? 20}
                total={transactionsQuery.data?.total ?? 0}
                onPageChange={setPage}
              />
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
