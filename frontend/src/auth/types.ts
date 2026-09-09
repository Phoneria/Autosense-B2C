export interface User { id: number | string; email: string; features: Record<string, boolean>; }
export interface AuthResponse { status: number; data?: { flows?: { id: string; is_pending?: boolean }[] }; errors?: { code: string; message: string; param?: string }[]; meta?: { is_authenticated?: boolean }; }
