"use client";

import { useEffect, useState } from "react";
import { useRouter, useParams } from "next/navigation";
import { useIsAuthenticated } from "@/hooks/use-auth";
import { useProducts } from "@/hooks/use-products";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { ProductList } from "@/components/products/product-list";
import { AddProductDialog } from "@/components/products/add-product-dialog";
import { guildsApi, Guild } from "@/lib/api";
import { ArrowLeft, Server, Loader2, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";

export default function ServerDetailPage() {
  const { guildId } = useParams<{ guildId: string }>();
  const { isAuthenticated, isLoading: authLoading } = useIsAuthenticated();
  const router = useRouter();
  const [guild, setGuild] = useState<Guild | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const numericGuildId = parseInt(guildId, 10);
  const { data: products, isLoading: productsLoading } = useProducts(
    isNaN(numericGuildId) ? undefined : numericGuildId
  );

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/");
    }
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    if (isAuthenticated && guildId) {
      guildsApi
        .get(guildId)
        .then(setGuild)
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false));
    }
  }, [isAuthenticated, guildId]);

  if (authLoading || loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-orange-500" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 container py-8">
        <div className="mb-8">
          <Button variant="ghost" asChild className="mb-4">
            <Link href="/servers">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Sunuculara Dön
            </Link>
          </Button>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              {guild?.icon_url ? (
                <img
                  src={guild.icon_url}
                  alt={guild.name}
                  className="h-16 w-16 rounded-full"
                />
              ) : (
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
                  <Server className="h-8 w-8 text-muted-foreground" />
                </div>
              )}
              <div>
                <h1 className="text-3xl font-bold">{guild?.name || "Sunucu"}</h1>
                <p className="text-muted-foreground">
                  {products?.length || 0} ürün takip ediliyor
                </p>
              </div>
            </div>
            <AddProductDialog guildId={numericGuildId} />
          </div>
        </div>

        {error && (
          <div className="mb-6 rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
            {error}
          </div>
        )}

        {productsLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-orange-500" />
          </div>
        ) : (
          <ProductList products={products || []} guildId={numericGuildId} />
        )}
      </main>
      <Footer />
    </div>
  );
}
