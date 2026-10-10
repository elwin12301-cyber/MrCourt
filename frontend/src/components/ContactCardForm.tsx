import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError } from '../services/api';
import { saveContactCard, useContactCard } from '../services/clientAdmin';
import { Button } from './ui';

/** The details an advocate chooses to show clients. A field left empty is never shown. */
export function ContactCardForm() {
  const { data } = useContactCard();
  const client = useQueryClient();
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [office, setOffice] = useState('');
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    if (data) {
      setPhone(data.phone ?? '');
      setEmail(data.email ?? '');
      setOffice(data.office ?? '');
    }
  }, [data]);

  return (
    <form
      className="card"
      onSubmit={async (event) => {
        event.preventDefault();
        setNote(null);
        try {
          await saveContactCard({ phone: phone || null, email: email || null, office: office || null });
          await client.invalidateQueries({ queryKey: ['contact-card'] });
          setNote('Saved. Clients see only the fields you have filled in.');
        } catch (e) {
          setNote(e instanceof ApiError ? e.message : 'Could not save.');
        }
      }}
      style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
    >
      <h2>What clients see about you</h2>
      <p className="fine" style={{ margin: 0 }}>
        Your name and verification status are always shown. Add contact details only if you want clients to have them.
      </p>
      <label className="field" htmlFor="cc-phone">
        Phone
        <input id="cc-phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} />
      </label>
      <label className="field" htmlFor="cc-email">
        Email
        <input id="cc-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      </label>
      <label className="field" htmlFor="cc-office">
        Office address
        <input id="cc-office" value={office} onChange={(e) => setOffice(e.target.value)} />
      </label>
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <Button type="submit" small>Save contact details</Button>
        {note && <span className="fine" role="status">{note}</span>}
      </div>
    </form>
  );
}
