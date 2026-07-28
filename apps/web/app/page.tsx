"use client";

import Link from "next/link";
import { useIsAuthenticated } from "@/hooks/use-auth";
import { authApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { TrendingUp, ArrowRight, Shield, Bell, BarChart3, Users } from "lucide-react";
import { ThemeToggle } from "@/components/shared/theme-toggle";

const features = [
  {
    icon: Bell,
    title: "Fiyat Uyarıları",
    description: "Fiyatlar düştüğünde veya arttığında anında bildirim alın.",
  },
  {
    icon: BarChart3,
    title: "Fiyat Grafiği",
    description: "Ürün fiyatlarının zaman içindeki değişimini takip edin.",
  },
  {
    icon: Shield,
    title: "Güvenli Takip",
    description: "Trendyol'dan güvenli bir şekilde ürün bilgilerini çekiyoruz.",
  },
  {
    icon: Users,
    title: "Sunucu Entegrasyonu",
    description: "Discord sunucularınızda fiyat uyarıları gönderin.",
  },
];

export default function HomePage() {
  const { isAuthenticated, isLoading, user } = useIsAuthenticated();

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-14 items-center justify-between">
          <div className="flex items-center space-x-2">
            <TrendingUp className="h-6 w-6 text-orange-500" />
            <span className="font-bold">Trendcord</span>
          </div>
          <div className="flex items-center gap-4">
            <ThemeToggle />
            {isLoading ? (
              <Button disabled>Giriş yapılıyor...</Button>
            ) : isAuthenticated ? (
              <Button asChild>
                <Link href="/dashboard">
                  Dashboard
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            ) : (
              <Button asChild>
                <a href={authApi.login()}>
                  Discord ile Giriş Yap
                </a>
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero Section */}
        <section className="container flex flex-col items-center justify-center gap-4 py-20 text-center md:py-32">
          <div className="inline-flex items-center rounded-full border bg-muted/50 px-4 py-1.5 text-sm">
            <TrendingUp className="mr-2 h-4 w-4 text-orange-500" />
            Trendyol Fiyat Takip Botu
          </div>
          <h1 className="max-w-3xl text-4xl font-bold tracking-tighter sm:text-5xl md:text-6xl">
            Trendyol Ürünlerinizi
            <span className="text-orange-500"> Akıllıca</span> Takip Edin
          </h1>
          <p className="max-w-[600px] text-lg text-muted-foreground">
            Discord sunucularınız için otomatik fiyat takibi ve uyarıları.
            Fiyatlar düştüğünde haberdar olun, en iyi fırsatları kaçırmayın.
          </p>
          <div className="flex flex-col gap-4 sm:flex-row">
            <Button size="lg" asChild>
              <a href={isAuthenticated ? "/dashboard" : authApi.login()}>
                {isAuthenticated ? "Dashboard'a Git" : "Ücretsiz Başla"}
                <ArrowRight className="ml-2 h-4 w-4" />
              </a>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <a href="https://discord.gg/trendcord" target="_blank" rel="noopener noreferrer">
                Discord Sunucusu
              </a>
            </Button>
          </div>
        </section>

        {/* Features */}
        <section className="border-t bg-muted/50 py-20">
          <div className="container">
            <h2 className="mb-12 text-center text-3xl font-bold tracking-tighter">
              Neden Trendcord?
            </h2>
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
              {features.map((feature) => (
                <div
                  key={feature.title}
                  className="rounded-lg border bg-background p-6 shadow-sm transition-all hover:shadow-md"
                >
                  <feature.icon className="mb-4 h-8 w-8 text-orange-500" />
                  <h3 className="mb-2 font-semibold">{feature.title}</h3>
                  <p className="text-sm text-muted-foreground">{feature.description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="container py-20 text-center">
          <h2 className="mb-4 text-3xl font-bold tracking-tighter">
            Hemen Başlayın
          </h2>
          <p className="mb-8 text-muted-foreground">
            Discord hesabınızla giriş yapın ve fiyat takibine başlayın.
          </p>
          <Button size="lg" asChild>
            <a href={isAuthenticated ? "/dashboard" : authApi.login()}>
              {isAuthenticated ? "Dashboard'a Git" : "Discord ile Giriş Yap"}
              <ArrowRight className="ml-2 h-4 w-4" />
            </a>
          </Button>
        </section>
      </main>

      <footer className="border-t py-6">
        <div className="container flex flex-col items-center justify-between gap-4 md:flex-row">
          <div className="flex items-center space-x-2">
            <TrendingUp className="h-5 w-5 text-orange-500" />
            <span className="text-sm font-semibold">Trendcord</span>
          </div>
          <p className="text-center text-sm text-muted-foreground">
            2024 Trendcord. Tüm hakları saklıdır.
          </p>
        </div>
      </footer>
    </div>
  );
}
