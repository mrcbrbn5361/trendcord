"use client";

import { Guild } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Users, Package } from "lucide-react";
import Image from "next/image";
import Link from "next/link";

interface ServerCardProps {
  guild: Guild;
}

export function ServerCard({ guild }: ServerCardProps) {
  return (
    <Link href={`/servers/${guild.discord_id}`}>
      <Card className="group overflow-hidden transition-all hover:shadow-lg hover:border-primary/50 cursor-pointer">
        <div className="relative aspect-video overflow-hidden bg-muted">
          {guild.icon_url ? (
            <Image
              src={guild.icon_url}
              alt={guild.name}
              fill
              className="object-cover transition-transform group-hover:scale-105"
            />
          ) : (
            <div className="flex h-full items-center justify-center">
              <span className="text-4xl font-bold text-muted-foreground">
                {guild.name.charAt(0)}
              </span>
            </div>
          )}
        </div>
        <CardContent className="p-4">
          <h3 className="font-semibold group-hover:text-primary transition-colors">
            {guild.name}
          </h3>
          <div className="mt-2 flex items-center gap-4 text-sm text-muted-foreground">
            <span className="flex items-center gap-1">
              <Package className="h-3.5 w-3.5" />
              {guild.product_count} ürün
            </span>
            <span className="flex items-center gap-1">
              <Users className="h-3.5 w-3.5" />
              {guild.owner_id ? "Sahip" : "Üye"}
            </span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
