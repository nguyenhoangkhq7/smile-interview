import axiosClient from '@/lib/axiosClient';
import type {
  AdminUserDetail, AdminUserPage, AdminUserStatus, PasswordSetupLink, UserCatalogFilter,
} from '@/components/features/admin/users/types';

const baseURL = '/';
const path = '/api/admin/users';

function params(filter: UserCatalogFilter) {
  return {
    search: filter.search.trim() || undefined,
    role: filter.role || undefined,
    status: filter.status || undefined,
  };
}

export const adminUsers = {
  async list(filter: UserCatalogFilter, page: number, signal: AbortSignal) {
    return (await axiosClient.get<AdminUserPage>(path, { baseURL, signal, params: { ...params(filter), page } })).data;
  },
  async detail(id: string, signal: AbortSignal) {
    return (await axiosClient.get<AdminUserDetail>(path + '/' + id, { baseURL, signal })).data;
  },
  async create(input: { fullName: string; email: string }) {
    return (await axiosClient.post<PasswordSetupLink>(path, input, { baseURL })).data;
  },
  async changeStatus(id: string, status: AdminUserStatus, reason?: string) {
    await axiosClient.patch(path + '/' + id + '/status', { status, reason }, { baseURL });
  },
  async resetPassword(id: string) {
    return (await axiosClient.post<PasswordSetupLink>(path + '/' + id + '/password-setup', undefined, { baseURL })).data;
  },
  async export(filter: UserCatalogFilter) {
    return (await axiosClient.get<Blob>(path + '/export', { baseURL, responseType: 'blob', params: params(filter) })).data;
  },
};
