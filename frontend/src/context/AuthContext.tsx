"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { supabase, hasSupabase } from '@/lib/supabase';
import { readSession, writeSession, clearSession, type AppSession, type UserRole } from '@/lib/session';
import { syncBackendAuthTokenWithPassword } from '@/lib/backend-auth';

interface AuthContextValue {
	session: AppSession | null;
	loading: boolean;
	login: (email: string, password: string) => Promise<void>;
	logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function inferName(email: string): string {
	const handle = email.split('@')[0] ?? 'User';
	return handle
		.split(/[._-]/)
		.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
		.join(' ');
}

function inferRoleFromEmail(email: string): UserRole {
	if (email.toLowerCase().includes('admin')) {
		return 'admin';
	}
	if (email.toLowerCase().includes('manager')) {
		return 'manager';
	}
	return email.toLowerCase().includes('hr') ? 'hr' : 'employee';
}

export function AuthProvider({ children }: { children: ReactNode }) {
	const router = useRouter();
	const [session, setSession] = useState<AppSession | null>(null);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		const stored = readSession();
		if (stored) {
			setSession(stored);
		}
		setLoading(false);
	}, []);

	async function login(email: string, password: string): Promise<void> {
		let role: UserRole = inferRoleFromEmail(email);
		let name = inferName(email);
		let userId: string | undefined;
		const loginAtMs = Date.now();
		const breakReminderAtMs = loginAtMs + 2 * 60 * 60 * 1000;
		const secondBreakReminderAtMs = loginAtMs + Math.round((5 + Math.random()) * 60 * 60 * 1000);

		if (hasSupabase && supabase) {
			const { data, error: authError } = await supabase.auth.signInWithPassword({ email, password });
			if (authError) {
				throw authError;
			}

			userId = data.user?.id;

			const { data: profile } = await supabase
				.from('users')
				.select('id,email,role,name')
				.eq('email', email)
				.maybeSingle();

			if (profile && profile.role) {
				role = profile.role as UserRole;
				name = profile.name ?? name;
				userId = profile.id ?? userId;
			}
		}

		const newSession: AppSession = {
			id: userId,
			email,
			name,
			role,
			loginAtMs,
			breakReminderAtMs,
			secondBreakReminderAtMs,
		};
		writeSession(newSession);
		setSession(newSession);

		await syncBackendAuthTokenWithPassword(email, password);

		const redirect = role === 'admin'
			? '/dashboard'
			: role === 'hr'
				? '/dashboard'
				: role === 'manager'
					? '/manager'
					: '/employee';
		router.replace(redirect);
	}

	function logout(): void {
		clearSession();
		setSession(null);
		if (hasSupabase && supabase) {
			supabase.auth.signOut();
		}
		router.replace('/login');
	}

	return (
		<AuthContext.Provider value={{ session, loading, login, logout }}>
			{children}
		</AuthContext.Provider>
	);
}

export function useAuth(): AuthContextValue {
	const context = useContext(AuthContext);
	if (!context) {
		throw new Error('useAuth must be used within an AuthProvider');
	}
	return context;
}