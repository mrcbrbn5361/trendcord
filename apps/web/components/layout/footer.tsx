import { TrendingUp } from "lucide-react";

export function Footer() {
  return (
    <footer className="border-t bg-muted/50">
      <div className="container py-6 md:py-8">
        <div className="flex flex-col items-center justify-between gap-4 md:flex-row">
          <div className="flex items-center space-x-2">
            <TrendingUp className="h-5 w-5 text-orange-500" />
            <span className="text-sm font-semibold">Trendcord</span>
          </div>
          <p className="text-center text-sm text-muted-foreground">
            Trendyol fiyat takip botu. Discord sunucularınız için fiyat uyarıları.
          </p>
          <div className="flex items-center space-x-4 text-sm text-muted-foreground">
            <a href="https://discord.gg/trendcord" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">
              Discord
            </a>
            <a href="https://github.com/mrcbrbn5361/trendcord" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">
              GitHub
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
