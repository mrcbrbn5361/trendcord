"use client";

import { PriceHistory } from "@/lib/api";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { format } from "date-fns";
import { tr } from "date-fns/locale";

interface PriceChartProps {
  data: PriceHistory[];
}

export function PriceChart({ data }: PriceChartProps) {
  if (data.length === 0) {
    return (
      <div className="flex h-[300px] items-center justify-center rounded-lg border border-dashed">
        <p className="text-sm text-muted-foreground">Henüz fiyat geçmişi yok</p>
      </div>
    );
  }

  const chartData = data
    .map((item) => ({
      date: format(new Date(item.timestamp), "dd MMM", { locale: tr }),
      price: item.price,
      timestamp: item.timestamp,
    }))
    .reverse();

  return (
    <div className="h-[300px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
          <XAxis
            dataKey="date"
            className="text-xs"
            tick={{ fill: "hsl(var(--muted-foreground))" }}
          />
          <YAxis
            className="text-xs"
            tick={{ fill: "hsl(var(--muted-foreground))" }}
            tickFormatter={(value) => `${value.toLocaleString("tr-TR")} TL`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "8px",
            }}
            labelStyle={{ color: "hsl(var(--foreground))" }}
            formatter={(value: number) => [
              `${value.toLocaleString("tr-TR")} TL`,
              "Fiyat",
            ]}
          />
          <Line
            type="monotone"
            dataKey="price"
            stroke="hsl(24.6, 95%, 53.1%)"
            strokeWidth={2}
            dot={{ fill: "hsl(24.6, 95%, 53.1%)", strokeWidth: 2 }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
