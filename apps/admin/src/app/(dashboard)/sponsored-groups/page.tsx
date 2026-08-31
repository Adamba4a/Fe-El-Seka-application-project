"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createAdminBrowserClient } from "@/lib/supabase/browser-client";
import {
  createOrUpgrade,
  addFunds,
  listMembers,
  listSponsoredGroups,
  setDashboardContact,
  addSponsorDomain,
  removeSponsorDomain,
  deleteSponsoredGroup,
  unsponsorGroup,
  type SponsoredGroupSummary,
  type GroupMember,
} from "@/lib/api/admin-sponsored-groups";

const sb = createAdminBrowserClient();

export default function SponsoredGroupsPage() {
  const [groups, setGroups] = useState<SponsoredGroupSummary[]>([]);
  const [loadingGroups, setLoadingGroups] = useState(true);
  const [copiedId, setCopiedId] = useState("");

  const [domains, setDomains] = useState("");
  const [name, setName] = useState("");
  const [fundedBalance, setFundedBalance] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [result, setResult] = useState<SponsoredGroupSummary | null>(null);

  const [fundsGroupId, setFundsGroupId] = useState("");
  const [fundsAmount, setFundsAmount] = useState("");
  const [addingFunds, setAddingFunds] = useState(false);

  const [contactGroupId, setContactGroupId] = useState("");
  const [members, setMembers] = useState<GroupMember[]>([]);
  const [loadingMembers, setLoadingMembers] = useState(false);
  const [contactUserId, setContactUserId] = useState("");
  const [settingContact, setSettingContact] = useState(false);

  const [domainsGroupId, setDomainsGroupId] = useState("");
  const [newDomain, setNewDomain] = useState("");
  const [removeDomainValue, setRemoveDomainValue] = useState("");
  const [domainsResult, setDomainsResult] = useState<string[] | null>(null);
  const [managingDomains, setManagingDomains] = useState(false);

  const [pendingActionId, setPendingActionId] = useState("");

  async function getToken() {
    const { data } = await sb.auth.getSession();
    return data.session?.access_token ?? "";
  }

  async function refreshGroups() {
    setLoadingGroups(true);
    try {
      const token = await getToken();
      setGroups(await listSponsoredGroups(token));
    } catch (err: any) {
      setError(err?.message ?? "Failed to load sponsored groups.");
    } finally {
      setLoadingGroups(false);
    }
  }

  useEffect(() => {
    refreshGroups();
  }, []);

  function useGroupId(groupId: string) {
    setDomainsGroupId(groupId);
    setFundsGroupId(groupId);
    setContactGroupId(groupId);
    setDomainsResult(null);
    setMembers([]);
    setContactUserId("");
  }

  async function copyGroupId(groupId: string) {
    try {
      await navigator.clipboard.writeText(groupId);
      setCopiedId(groupId);
      setTimeout(() => setCopiedId(""), 1500);
    } catch {
      // Clipboard API can be unavailable (e.g. non-HTTPS) — the ID is still
      // selectable/visible in the table, so this is a nice-to-have only.
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setNotice("");
    setCreating(true);
    try {
      const token = await getToken();
      const domainList = domains
        .split(",")
        .map((d) => d.trim())
        .filter(Boolean);
      const group = await createOrUpgrade(token, domainList, fundedBalance, name.trim());
      setResult(group);
      setNotice("Sponsored group created.");
      await refreshGroups();
    } catch (err: any) {
      setError(err?.message ?? "Failed to create sponsored group.");
    } finally {
      setCreating(false);
    }
  }

  async function handleAddDomain(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setNotice("");
    setManagingDomains(true);
    try {
      const token = await getToken();
      const res = await addSponsorDomain(token, domainsGroupId.trim(), newDomain.trim());
      setDomainsResult(res.domains);
      setNewDomain("");
      setNotice("Domain added.");
      await refreshGroups();
    } catch (err: any) {
      setError(err?.message ?? "Failed to add domain.");
    } finally {
      setManagingDomains(false);
    }
  }

  async function handleRemoveDomain(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setNotice("");
    setManagingDomains(true);
    try {
      const token = await getToken();
      const res = await removeSponsorDomain(token, domainsGroupId.trim(), removeDomainValue.trim());
      setDomainsResult(res.domains);
      setRemoveDomainValue("");
      setNotice("Domain removed.");
      await refreshGroups();
    } catch (err: any) {
      setError(err?.message ?? "Failed to remove domain.");
    } finally {
      setManagingDomains(false);
    }
  }

  async function handleAddFunds(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setNotice("");
    setAddingFunds(true);
    try {
      const token = await getToken();
      const res = await addFunds(token, fundsGroupId.trim(), fundsAmount);
      setNotice(
        `Funds added. New balance: ${Number(res.new_funded_balance_egp).toLocaleString("en-EG", {
          minimumFractionDigits: 2,
        })} EGP`
      );
      await refreshGroups();
    } catch (err: any) {
      setError(err?.message ?? "Failed to add funds.");
    } finally {
      setAddingFunds(false);
    }
  }

  async function handleLoadMembers(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setNotice("");
    setMembers([]);
    setContactUserId("");
    setLoadingMembers(true);
    try {
      const token = await getToken();
      const res = await listMembers(token, contactGroupId.trim());
      setMembers(res);
    } catch (err: any) {
      setError(err?.message ?? "Failed to load group members.");
    } finally {
      setLoadingMembers(false);
    }
  }

  async function handleUnsponsor(group: SponsoredGroupSummary) {
    const balanceNote =
      Number(group.funded_balance_egp) > 0
        ? ` This will clear its remaining funded balance of ${Number(group.funded_balance_egp).toLocaleString("en-EG", { minimumFractionDigits: 2 })} EGP.`
        : "";
    if (
      !window.confirm(
        `Convert "${group.name}" back to a regular, unsponsored group?${balanceNote} Its eligible domains will be released. This cannot be undone.`
      )
    ) {
      return;
    }
    setError("");
    setNotice("");
    setPendingActionId(group.id);
    try {
      const token = await getToken();
      const res = await unsponsorGroup(token, group.id);
      setNotice(
        `"${group.name}" is no longer sponsored.${
          Number(res.cleared_funded_balance_egp) > 0
            ? ` Cleared balance: ${Number(res.cleared_funded_balance_egp).toLocaleString("en-EG", { minimumFractionDigits: 2 })} EGP.`
            : ""
        }`
      );
      await refreshGroups();
    } catch (err: any) {
      setError(err?.message ?? "Failed to unsponsor group.");
    } finally {
      setPendingActionId("");
    }
  }

  async function handleDelete(group: SponsoredGroupSummary) {
    const balanceNote =
      Number(group.funded_balance_egp) > 0
        ? ` This will clear its remaining funded balance of ${Number(group.funded_balance_egp).toLocaleString("en-EG", { minimumFractionDigits: 2 })} EGP.`
        : "";
    if (
      !window.confirm(
        `Delete the sponsored group "${group.name}"?${balanceNote} Its eligible domains will be released and members will lose access to it. This cannot be undone.`
      )
    ) {
      return;
    }
    setError("");
    setNotice("");
    setPendingActionId(group.id);
    try {
      const token = await getToken();
      await deleteSponsoredGroup(token, group.id);
      setNotice(`"${group.name}" was deleted.`);
      await refreshGroups();
    } catch (err: any) {
      setError(err?.message ?? "Failed to delete group.");
    } finally {
      setPendingActionId("");
    }
  }

  async function handleSetContact(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setNotice("");
    setSettingContact(true);
    try {
      const token = await getToken();
      await setDashboardContact(token, contactGroupId.trim(), contactUserId);
      const assignedName = members.find((m) => m.user_id === contactUserId)?.display_name ?? contactUserId;
      setNotice(`Dashboard contact assigned: ${assignedName}.`);
      await refreshGroups();
    } catch (err: any) {
      setError(err?.message ?? "Failed to assign dashboard contact.");
    } finally {
      setSettingContact(false);
    }
  }

  return (
    <main className="p-8 space-y-8 max-w-2xl">
      <div className="flex items-center gap-4">
        <Link href="/" className="text-sm text-blue-600 hover:underline">← Dashboard</Link>
        <h1 className="text-2xl font-semibold">Sponsored Groups</h1>
      </div>

      {(notice || error) && (
        <div className="sticky top-2 z-10 space-y-2">
          {notice && (
            <div className="rounded border border-green-200 bg-green-50 text-green-800 text-sm p-3 shadow-sm">
              {notice}
            </div>
          )}
          {error && (
            <p className="rounded border border-red-200 bg-red-50 text-red-600 text-sm p-3 shadow-sm">{error}</p>
          )}
        </div>
      )}

      <section className="space-y-4 border rounded p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-medium">Sponsored groups</h2>
          <button
            type="button"
            onClick={refreshGroups}
            disabled={loadingGroups}
            className="text-sm text-blue-600 hover:underline disabled:text-gray-400"
          >
            {loadingGroups ? "Refreshing…" : "Refresh"}
          </button>
        </div>
        <p className="text-sm text-gray-500">
          Every group ID you need for the sections below — click one to fill in the Group ID
          fields, or copy it directly.
        </p>
        {loadingGroups ? (
          <p className="text-sm text-gray-500">Loading…</p>
        ) : groups.length === 0 ? (
          <p className="text-sm text-gray-500">No sponsored groups yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-gray-500 border-b">
                  <th className="py-2 pr-3">Name</th>
                  <th className="py-2 pr-3">Group ID</th>
                  <th className="py-2 pr-3">Domains</th>
                  <th className="py-2 pr-3">Balance (EGP)</th>
                  <th className="py-2 pr-3">Dashboard contact</th>
                  <th className="py-2"></th>
                </tr>
              </thead>
              <tbody>
                {groups.map((g) => (
                  <tr key={g.id} className="border-b last:border-0 align-top">
                    <td className="py-2 pr-3">{g.name}</td>
                    <td className="py-2 pr-3 font-mono text-xs">
                      <button
                        type="button"
                        onClick={() => copyGroupId(g.id)}
                        title={g.id}
                        className="hover:underline"
                      >
                        {g.id.slice(0, 8)}… {copiedId === g.id ? "(copied)" : ""}
                      </button>
                    </td>
                    <td className="py-2 pr-3">{g.sponsor_domains.join(", ") || "(none)"}</td>
                    <td className="py-2 pr-3">
                      {Number(g.funded_balance_egp).toLocaleString("en-EG", { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-2 pr-3 font-mono text-xs">
                      {g.dashboard_contact_user_id ? g.dashboard_contact_user_id.slice(0, 8) + "…" : "(unassigned)"}
                    </td>
                    <td className="py-2 space-x-3 whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => useGroupId(g.id)}
                        className="text-blue-600 hover:underline"
                      >
                        Use ID
                      </button>
                      <button
                        type="button"
                        onClick={() => handleUnsponsor(g)}
                        disabled={pendingActionId === g.id}
                        className="text-amber-600 hover:underline disabled:text-gray-400"
                      >
                        Unsponsor
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDelete(g)}
                        disabled={pendingActionId === g.id}
                        className="text-red-600 hover:underline disabled:text-gray-400"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="space-y-4 border rounded p-6">
        <h2 className="text-lg font-medium">Create a sponsored group</h2>
        <p className="text-sm text-gray-500">
          Groups have no type — any org-verified user can join any group. Sponsorship eligibility
          is decided separately, by whichever email domains you list here (e.g. every faculty
          subdomain of one university), so students on different domains still share one group.
        </p>
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Eligible domains (comma-separated)</label>
            <input
              type="text"
              required
              value={domains}
              onChange={(e) => setDomains(e.target.value)}
              placeholder="eng-st.cu.edu.eg, cu.edu.eg"
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Group name (optional)</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Initial funded balance (EGP)</label>
            <input
              type="number"
              step="0.01"
              min="0"
              required
              value={fundedBalance}
              onChange={(e) => setFundedBalance(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={creating}
            className="bg-gray-900 text-white text-sm px-4 py-2 rounded disabled:bg-gray-400"
          >
            {creating ? "Submitting…" : "Create sponsored group"}
          </button>
        </form>

        {result && (
          <div className="text-sm bg-gray-50 border rounded p-3 space-y-1">
            <p><span className="text-gray-500">Group ID:</span> {result.id}</p>
            <p><span className="text-gray-500">Name:</span> {result.name}</p>
            <p><span className="text-gray-500">Eligible domains:</span> {result.sponsor_domains.join(", ")}</p>
            <p>
              <span className="text-gray-500">Funded balance:</span>{" "}
              {Number(result.funded_balance_egp).toLocaleString("en-EG", { minimumFractionDigits: 2 })} EGP
            </p>
          </div>
        )}
      </section>

      <section className="space-y-4 border rounded p-6">
        <h2 className="text-lg font-medium">Manage a sponsored group&rsquo;s eligible domains</h2>
        <p className="text-sm text-gray-500">
          Add another subdomain to fold more students into an existing sponsored group instead of
          fragmenting them into a new one, or remove one that no longer applies.
        </p>
        <div>
          <label className="block text-sm font-medium mb-1">Group ID</label>
          <input
            type="text"
            required
            value={domainsGroupId}
            onChange={(e) => setDomainsGroupId(e.target.value)}
            className="w-full border rounded px-3 py-2 text-sm"
          />
        </div>
        <form onSubmit={handleAddDomain} className="flex items-end gap-3">
          <div className="flex-1">
            <label className="block text-sm font-medium mb-1">Add domain</label>
            <input
              type="text"
              required
              value={newDomain}
              onChange={(e) => setNewDomain(e.target.value)}
              placeholder="eng-st.cu.edu.eg"
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={managingDomains || !domainsGroupId.trim()}
            className="bg-gray-900 text-white text-sm px-4 py-2 rounded disabled:bg-gray-400"
          >
            {managingDomains ? "Submitting…" : "Add"}
          </button>
        </form>
        <form onSubmit={handleRemoveDomain} className="flex items-end gap-3">
          <div className="flex-1">
            <label className="block text-sm font-medium mb-1">Remove domain</label>
            <input
              type="text"
              required
              value={removeDomainValue}
              onChange={(e) => setRemoveDomainValue(e.target.value)}
              placeholder="eng-st.cu.edu.eg"
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={managingDomains || !domainsGroupId.trim()}
            className="bg-gray-200 text-gray-900 text-sm px-4 py-2 rounded disabled:opacity-50"
          >
            {managingDomains ? "Submitting…" : "Remove"}
          </button>
        </form>

        {domainsResult && (
          <div className="text-sm bg-gray-50 border rounded p-3">
            <span className="text-gray-500">Eligible domains:</span>{" "}
            {domainsResult.length > 0 ? domainsResult.join(", ") : "(none)"}
          </div>
        )}
      </section>

      <section className="space-y-4 border rounded p-6">
        <h2 className="text-lg font-medium">Add funds to an existing sponsored group</h2>
        <form onSubmit={handleAddFunds} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Group ID</label>
            <input
              type="text"
              required
              value={fundsGroupId}
              onChange={(e) => setFundsGroupId(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Amount to add (EGP)</label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              required
              value={fundsAmount}
              onChange={(e) => setFundsAmount(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={addingFunds}
            className="bg-gray-900 text-white text-sm px-4 py-2 rounded disabled:bg-gray-400"
          >
            {addingFunds ? "Submitting…" : "Add funds"}
          </button>
        </form>
      </section>

      <section className="space-y-4 border rounded p-6">
        <h2 className="text-lg font-medium">Assign sponsorship dashboard contact</h2>
        <p className="text-sm text-gray-500">
          The dashboard contact must already be a member of the group.
        </p>
        <form onSubmit={handleLoadMembers} className="flex items-end gap-3">
          <div className="flex-1">
            <label className="block text-sm font-medium mb-1">Group ID</label>
            <input
              type="text"
              required
              value={contactGroupId}
              onChange={(e) => setContactGroupId(e.target.value)}
              className="w-full border rounded px-3 py-2 text-sm"
            />
          </div>
          <button
            type="submit"
            disabled={loadingMembers}
            className="bg-gray-200 text-gray-900 text-sm px-4 py-2 rounded disabled:opacity-50"
          >
            {loadingMembers ? "Loading…" : "Load members"}
          </button>
        </form>

        {members.length > 0 && (
          <form onSubmit={handleSetContact} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Member</label>
              <select
                required
                value={contactUserId}
                onChange={(e) => setContactUserId(e.target.value)}
                className="w-full border rounded px-3 py-2 text-sm"
              >
                <option value="" disabled>Select a member…</option>
                {members.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.display_name} ({m.role})
                  </option>
                ))}
              </select>
            </div>
            <button
              type="submit"
              disabled={settingContact || !contactUserId}
              className="bg-gray-900 text-white text-sm px-4 py-2 rounded disabled:bg-gray-400"
            >
              {settingContact ? "Submitting…" : "Assign dashboard contact"}
            </button>
          </form>
        )}
      </section>
    </main>
  );
}
