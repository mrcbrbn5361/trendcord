"use client";

import { useQuery } from "@tanstack/react-query";
import { authApi, User } from "@/lib/api";

export function useUser() {
  return useQuery({
    queryKey: ["user"],
    queryFn: authApi.me,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}

export function useIsAuthenticated() {
  const { data: user, isLoading } = useUser();
  
  return {
    isAuthenticated: !!user,
    isLoading,
    user,
  };
}
