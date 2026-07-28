"use client";

import { Product } from "@/lib/api";
import { ProductCard } from "./product-card";
import { Package } from "lucide-react";

interface ProductListProps {
  products: Product[];
  guildId: number;
}

export function ProductList({ products, guildId }: ProductListProps) {
  if (products.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-8 text-center">
        <Package className="h-12 w-12 text-muted-foreground" />
        <h3 className="mt-4 text-lg font-semibold">Ürün Bulunamadı</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          Henüz ürün eklenmemiş. İlk ürününüzü ekleyerek başlayın.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {products.map((product) => (
        <ProductCard key={product.id} product={product} guildId={guildId} />
      ))}
    </div>
  );
}
