"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { productsApi, Product, CreateProduct, UpdateProduct } from "@/lib/api";
import { toast } from "sonner";

export function useProducts(guildId?: number) {
  return useQuery({
    queryKey: ["products", guildId],
    queryFn: () => productsApi.list(guildId ? { guild_id: guildId } : undefined),
  });
}

export function useProduct(productId: string) {
  return useQuery({
    queryKey: ["product", productId],
    queryFn: () => productsApi.get(productId),
    enabled: !!productId,
  });
}

export function useProductHistory(productId: string) {
  return useQuery({
    queryKey: ["product-history", productId],
    queryFn: () => productsApi.history(productId),
    enabled: !!productId,
  });
}

export function useCreateProduct() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: CreateProduct) => productsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      toast.success("Ürün başarıyla eklendi");
    },
    onError: (error: Error) => {
      toast.error(error.message || "Ürün eklenirken hata oluştu");
    },
  });
}

export function useUpdateProduct() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ productId, data }: { productId: string; data: UpdateProduct }) =>
      productsApi.update(productId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      toast.success("Ürün başarıyla güncellendi");
    },
    onError: (error: Error) => {
      toast.error(error.message || "Ürün güncellenirken hata oluştu");
    },
  });
}

export function useDeleteProduct() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (productId: string) => productsApi.delete(productId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      toast.success("Ürün başarıyla silindi");
    },
    onError: (error: Error) => {
      toast.error(error.message || "Ürün silinirken hata oluştu");
    },
  });
}
