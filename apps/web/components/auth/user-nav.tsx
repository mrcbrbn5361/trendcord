"use client";

import { useIsAuthenticated } from "@/hooks/use-auth";
import { authApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { LogIn, LogOut, User } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import Image from "next/image";

export function UserNav() {
  const { isAuthenticated, isLoading, user } = useIsAuthenticated();

  if (isLoading) {
    return (
      <Button variant="ghost" size="icon" disabled>
        <User className="h-4 w-4 animate-pulse" />
      </Button>
    );
  }

  if (!isAuthenticated) {
    return (
      <Button asChild variant="default" size="sm">
        <a href={authApi.login()}>
          <LogIn className="mr-2 h-4 w-4" />
          Giriş Yap
        </a>
      </Button>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="relative h-8 w-8 rounded-full">
          {user?.avatar_url ? (
            <Image
              src={user.avatar_url}
              alt={user.username}
              width={32}
              height={32}
              className="rounded-full"
            />
          ) : (
            <User className="h-4 w-4" />
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56" align="end" forceMount>
        <div className="flex items-center gap-2 p-2">
          <div className="flex flex-col space-y-1 leading-none">
            <p className="font-medium">{user?.username}</p>
          </div>
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <a href="/dashboard">
            <User className="mr-2 h-4 w-4" />
            Dashboard
          </a>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <a href="/api/v1/auth/logout">
            <LogOut className="mr-2 h-4 w-4" />
            Çıkış Yap
          </a>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
