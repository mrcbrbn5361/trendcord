"use client";

import { useState } from "react";
import { useCreateProduct } from "@/hooks/use-products";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Plus, Loader2 } from "lucide-react";
import { toast } from "sonner";

interface AddProductDialogProps {
  guildId: number;
}

export function AddProductDialog({ guildId }: AddProductDialogProps) {
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [channelId, setChannelId] = useState("");
  const createProduct = useCreateProduct();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!url.trim()) {
      toast.error("Ürün URL'si gerekli");
      return;
    }

    try {
      await createProduct.mutateAsync({
        product_id: extractProductId(url),
        name: "Yükleniyor...",
        url: url.trim(),
        guild_id: guildId,
        channel_id: channelId || undefined,
      });
      setOpen(false);
      setUrl("");
      setChannelId("");
    } catch {
      // Error handled by mutation
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Ürün Ekle
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Yeni Ürün Ekle</DialogTitle>
            <DialogDescription>
              Trendyol ürün URL'sini yapıştırarak fiyat takibine başlayın.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="url">Ürün URL'si</Label>
              <Input
                id="url"
                placeholder="https://www.trendyol.com/..."
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="channel">Kanal ID (Opsiyonel)</Label>
              <Input
                id="channel"
                placeholder="Discord kanal ID'si"
                value={channelId}
                onChange={(e) => setChannelId(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              İptal
            </Button>
            <Button type="submit" disabled={createProduct.isPending}>
              {createProduct.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Ekle
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function extractProductId(url: string): string {
  const match = url.match(/-p-(\d+)/);
  return match ? match[1] : Date.now().toString();
}
