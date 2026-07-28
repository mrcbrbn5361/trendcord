"use client";

import { Product } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TrendingDown, TrendingUp, ExternalLink, Trash2 } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { useDeleteProduct } from "@/hooks/use-products";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

interface ProductCardProps {
  product: Product;
  guildId: number;
}

export function ProductCard({ product, guildId }: ProductCardProps) {
  const deleteProduct = useDeleteProduct();
  const priceDiff = product.original_price - product.current_price;
  const pricePercent = product.original_price > 0
    ? ((priceDiff / product.original_price) * 100).toFixed(1)
    : "0";
  const isDiscounted = priceDiff > 0;

  return (
    <Card className="group overflow-hidden transition-all hover:shadow-lg">
      <div className="relative aspect-square overflow-hidden bg-muted">
        {product.image_url ? (
          <Image
            src={product.image_url}
            alt={product.name}
            fill
            className="object-cover transition-transform group-hover:scale-105"
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
      <CardContent className="p-4">
        <Link href={`/servers/${guildId}/products/${product.product_id}`}>
          <h3 className="line-clamp-2 font-semibold hover:text-primary transition-colors">
            {product.name}
          </h3>
        </Link>
        <div className="mt-2 flex items-baseline gap-2">
          <span className="text-xl font-bold text-orange-500">
            {product.current_price.toLocaleString("tr-TR")} TL
          </span>
          {isDiscounted && (
            <span className="text-sm text-muted-foreground line-through">
              {product.original_price.toLocaleString("tr-TR")} TL
            </span>
          )}
        </div>
        {isDiscounted && (
          <div className="mt-1 flex items-center gap-1 text-sm text-green-600 dark:text-green-400">
            <TrendingDown className="h-3 w-3" />
            {priceDiff.toLocaleString("tr-TR")} TL tasarruf
          </div>
        )}
        <div className="mt-3 flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            Son güncelleme: {new Date(product.last_checked).toLocaleDateString("tr-TR")}
          </span>
          <div className="flex gap-1">
            <Button variant="ghost" size="icon" asChild>
              <a href={product.url} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="h-4 w-4" />
              </a>
            </Button>
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive">
                  <Trash2 className="h-4 w-4" />
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Ürünü Sil</AlertDialogTitle>
                  <AlertDialogDescription>
                    Bu ürünü silmek istediğinize emin misiniz? Bu işlem geri alınamaz.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>İptal</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={() => deleteProduct.mutate(String(product.id))}
                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                  >
                    Sil
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
