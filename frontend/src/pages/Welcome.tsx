import { Link, Navigate, useNavigate } from 'react-router-dom';
import { BrandPanel } from '../components/BrandPanel';
import { Icon } from '../components/Icon';
import { Button } from '../components/ui';
import { useMe } from '../services/auth';

export default function Welcome() {
  const navigate = useNavigate();
  const { data: me, isLoading } = useMe();
  if (isLoading) return null;
  if (me) return <Navigate to="/dashboard" replace />;

  return (
    <section className="split" id="welcome" data-screen="welcome">
      <BrandPanel>
        <h1>MrCourt</h1>
        <p className="lead">Trusted legal guidance, grounded in Indian law.</p>
        <ul>
          <li>
            <Icon name="check" />
            Covers BNS, BNSS, BSA and the Constitution
          </li>
          <li>
            <Icon name="check" />
            Every answer cites the Act, section or judgment
          </li>
          <li>
            <Icon name="check" />
            Private by design, aligned with the DPDP Act
          </li>
        </ul>
      </BrandPanel>
      <div className="panel" style={{ position: 'relative' }}>
        <div>
          <h2>Welcome</h2>
          <p className="sub">Choose how you would like to use MrCourt.</p>
          <Button variant="gold" onClick={() => navigate('/login/advocate')}>
            <Icon name="case" />
            I'm an Advocate
          </Button>
          <Button variant="ghost" onClick={() => navigate('/login/petitioner')}>
            <Icon name="user" />
            I'm a Petitioner
          </Button>
          <p className="fine">Informational guidance only. Not legal advice.</p>
        </div>
        {/* Out of the flow on purpose: the centred block stays exactly where the design puts it. */}
        <p className="fine adminlink">
          New to MrCourt? <Link to="/register">Create an account</Link> · <Link to="/login/admin">Administrator sign in</Link>
        </p>
      </div>
    </section>
  );
}
