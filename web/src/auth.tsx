import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type Me } from "./api";

type Ctx = { me: Me | null; inviteRequired: boolean; refresh: () => Promise<void>; setMe: (m: Me) => void };
const AuthCtx = createContext<Ctx>({ me: null, inviteRequired: false, refresh: async () => {}, setMe: () => {} });

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [inviteRequired, setInvite] = useState(false);
  const refresh = useCallback(async () => {
    try { setMe(await api.me()); } catch { setMe({ authenticated: false }); }
  }, []);
  useEffect(() => {
    api.csrf().then((r) => setInvite(r.invite_required)).catch(() => {}).finally(refresh);
  }, [refresh]);
  return <AuthCtx.Provider value={{ me, inviteRequired, refresh, setMe }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
