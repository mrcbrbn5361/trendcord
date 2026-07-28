"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useIsAuthenticated } from "@/hooks/use-auth";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { ServerCard } from "@/components/servers/server-card";
import { guildsApi, Guild } from "@/lib/api";
import { Server, Loader2 } from "lucide-react";

export default function ServersPage() {
  const { isAuthenticated, isLoading: authLoading } = useIsAuthenticated();
  const router = useRouter();
  const [guilds, setGuilds] = useState<Guild[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push("/");
    }
  }, [authLoading, isAuthenticated, router]);

  useEffect(() => {
    if (isAuthenticated) {
      guildsApi
        .list()
        .then(setGuilds)
        .catch((err) => setError(err.message))
        .finally(() => setLoading(false));
    }
  }, [isAuthenticated]);

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
          <h1 className="text-3xl font-bold">Sunucularım</h1>
          <p className="text-muted-foreground">
            Botun bulunduğu Discord sunucuları
          </p>
        </div>

        {error && (
          <div className="mb-6 rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
            {error}
          </div>
        )}

        {guilds.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-12 text-center">
            <Server className="h-12 w-12 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">Sunucu Bulunamadı</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Bot henüz hiçbir sunucuya eklenmemiş.
            </p>
            <a
              href="https://discord.com/oauth2/authorize?client_id=1371109119255248936&permissions=8&scope=bot"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-4 text-sm text-orange-500 hover:underline"
            >
              Botu sunucunuza ekleyin
            </a>
          </div>
        ) : (
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {guilds.map((guild) => (
              <ServerCard key={guild.id} guild={guild} />
            ))}
          </div>
        )}
      </main>
      <Footer />
    </div>
  );
}
