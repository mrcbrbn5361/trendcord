"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { useIsAuthenticated } from "@/hooks/use-auth";
import { useProduct, useProductHistory } from "@/hooks/use-products";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { PriceChart } from "@/components/products/price-chart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, ExternalLink, TrendingDown, TrendingUp, Loader2 } from "lucide-react";
import Link from "next/link";
import Image from "next/image";

export default function ProductDetailPage() {
  const { guildId, productId } = useParams<{
    guildId: string;
    productId: string;
  }>();
  const { isAuthenticated, isLoading: authLoading } = useIsAuthenticated();
  const router = useRouter();

  const { data: product, isLoading: productLoading } = useProduct(productId);
  const { data: history, isLoading: historyLoading } = useProductHistory(productId);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/");
    }
  }, [authLoading, isAuthenticated, router]);

  if (authLoading || productLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-orange-500" />
      </div>
    );
  }

  if (!product) {
    return (
      <div className="flex min-h-screen flex-col">
        <Header />
        <main className="flex-1 container py-8">
          <div className="text-center">
            <h1 className="text-2xl font-bold">Ürün Bulunamadı</h1>
            <p className="text-muted-foreground">Bu ürün mevcut değil.</p>
            <Button asChild className="mt-4">
              <Link href={`/servers/${guildId}`}>Geri Dön</Link>
            </Button>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  const priceDiff = product.original_price - product.current_price;
  const pricePercent =
    product.original_price > 0
      ? ((priceDiff / product.original_price) * 100).toFixed(1)
      : "0";
  const isDiscounted = priceDiff > 0;

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 container py-8">
        <div className="mb-8">
          <Button variant="ghost" asChild className="mb-4">
            <Link href={`/servers/${guildId}`}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              Geri Dön
            </Link>
          </Button>

          <div className="grid gap-8 lg:grid-cols-3">
            {/* Product Image */}
            <div className="lg:col-span-1">
              <div className="relative aspect-square overflow-hidden rounded-lg border bg-muted">
                {product.image_url ? (
                  <Image
                    src={product.image_url}
                    alt={product.name}
                    fill
                    className="object-cover"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-muted-foreground">
                    Görsel Yok
                  </div>
                )}
                {isDiscounted && (
                  <Badge variant="destructive" className="absolute top-2 right-2">
                    %{pricePercent} İndirim
                  </Badge>
                )}
              </div>
            </div>

            {/* Product Info */}
            <div className="lg:col-span-2 space-y-6">
              <div>
                <h1 className="text-2xl font-bold">{product.name}</h1>
                <a
                  href={product.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-orange-500 transition-colors mt-2"
                >
                  Trendyol'da Gör
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>

              <div className="flex items-baseline gap-4">
                <span className="text-3xl font-bold text-orange-500">
                  {product.current_price.toLocaleString("tr-TR")} TL
                </span>
                {isDiscounted && (
                  <>
                    <span className="text-lg text-muted-foreground line-through">
                      {product.original_price.toLocaleString("tr-TR")} TL
                    </span>
                    <div className="flex items-center gap-1 text-green-600 dark:text-green-400">
                      <TrendingDown className="h-4 w-4" />
                      {priceDiff.toLocaleString("tr-TR")} TL tasarruf
                    </div>
                  </>
                )}
              </div>

              <div className="text-sm text-muted-foreground">
                Son güncelleme:{" "}
                {new Date(product.last_checked).toLocaleString("tr-TR")}
              </div>
            </div>
          </div>
        </div>

        {/* Price History Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Fiyat Geçmişi</CardTitle>
          </CardHeader>
          <CardContent>
            {historyLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-orange-500" />
              </div>
            ) : (
              <PriceChart data={history || []} />
            )}
          </CardContent>
        </Card>
      </main>
      <Footer />
    </div>
  );
}
