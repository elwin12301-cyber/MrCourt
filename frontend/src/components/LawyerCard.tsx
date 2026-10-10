import type { Lawyer } from '../services/client';
import { Icon } from './Icon';
import { Chip } from './ui';

/** Who the client's lawyer is, and only the contact details the lawyer chose to share. */
export function LawyerCard({ lawyer }: { lawyer: Lawyer }) {
  if (!lawyer.available) {
    return (
      <div className="card">
        <h2 style={{ marginBottom: 8 }}>My lawyer</h2>
        <p className="sub" style={{ margin: 0 }}>
          Your lawyer is no longer available on MrCourt. Please contact them directly.
        </p>
      </div>
    );
  }
  const hasContact = lawyer.phone || lawyer.email || lawyer.office;
  return (
    <div className="card">
      <h2 style={{ marginBottom: 10 }}>My lawyer</h2>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <b>{lawyer.name}</b>
        {lawyer.verification_status === 'verified' && <Chip tone="ok">Bar Council verified</Chip>}
        {lawyer.verification_status === 'pending' && <Chip tone="soon">Verification pending</Chip>}
      </div>
      {lawyer.phone && (
        <div className="act">
          <span>Phone</span>
          <a href={`tel:${lawyer.phone.replace(/\s/g, '')}`}>{lawyer.phone}</a>
        </div>
      )}
      {lawyer.email && (
        <div className="act">
          <span>Email</span>
          <a href={`mailto:${lawyer.email}`}>{lawyer.email}</a>
        </div>
      )}
      {lawyer.office && (
        <div className="act">
          <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <Icon name="case" size={14} />
            Office
          </span>
          {lawyer.office}
        </div>
      )}
      {!hasContact && (
        <p className="fine" style={{ marginTop: 10 }}>
          Your lawyer has not added contact details here. You can still send them a question below.
        </p>
      )}
    </div>
  );
}
