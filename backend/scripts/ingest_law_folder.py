"""Adds a folder of law PDFs to the knowledge base as shared sources, so questions are answered from them.

Nothing is copied into the repository: the files are read from the folder you name, the text is
stored in the database, and the originals are kept in the (git-ignored) knowledge folder. It is safe
to run again: a source whose title already exists is skipped, and identical files are added once.

Usage (from the backend folder, with DATABASE_URL set to the database to fill):
    python scripts/ingest_law_folder.py --folder C:\\Users\\Paul\\Downloads
    python scripts/ingest_law_folder.py --folder C:\\Users\\Paul\\Downloads --only "Penal Code"

Then give the new passages meaning-based search data (slow on a free Voyage account):
    python -m mrcourt.services.embed_missing --pace 60
"""

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import mrcourt.models  # noqa: E402,F401
from mrcourt.config import get_settings  # noqa: E402
from mrcourt.db.base import get_engine  # noqa: E402
from mrcourt.models import KnowledgeDocument, User  # noqa: E402
from mrcourt.services import knowledge  # noqa: E402

NOTES = "M. S. Rama Rao class-room notes"

# file name -> (title, who wrote it). Listed in the order they are added, which is also the order
# their meaning-based search data is made, so the most used law comes first.
MANIFEST: list[tuple[str, str, str]] = [
    ("INDIAN_PENAL_CODE.pdf", "Indian Penal Code (IPC)", NOTES),
    ("CRIMINAL_PROCEDURE_CODE.pdf", "Code of Criminal Procedure (CrPC)", NOTES),
    ("EVIDENCE_ACT.pdf", "Indian Evidence Act", NOTES),
    ("law1.pdf", "The Constitution of India", "official text, 2024 edition"),
    ("CONSTITUTION_OF_INDIA.pdf", "Constitution of India", NOTES),
    ("NEGOTIABLE_INSTRUMENTS_ACT.pdf", "Negotiable Instruments Act", NOTES),
    ("CIVIL_PROCEDURE_CODE_FINAL2012.pdf", "Code of Civil Procedure (CPC)", NOTES),
    ("LIMITATION_ACT.pdf", "Limitation Act", NOTES),
    ("CONTRACT_Act_F.pdf", "Indian Contract Act", NOTES),
    ("CONTRACT-Specific_ReliefAct.pdf", "Specific Relief Act", NOTES),
    ("SALE_OF_GOODS_ACT.pdf", "Sale of Goods Act", NOTES),
    ("INDEMNITY_GUARANTEE_BAILMENT.pdf", "Indemnity, Guarantee and Bailment", NOTES),
    ("LAW_OF_AGENCY.pdf", "Law of Agency", NOTES),
    ("PARTNERSHIP_ACT.pdf", "Partnership Act", NOTES),
    ("COMPANY_LAW.pdf", "Company Law", NOTES),
    ("TRANSFER_OF _PROPERTY_ACT.pdf", "Transfer of Property Act", NOTES),
    ("INDIAN_REGISTRATION_ACT.pdf", "Indian Registration Act", NOTES),
    ("LAW_OF_EASEMENTS.pdf", "Law of Easements", NOTES),
    ("INDIAN_TRUSTS_ACT.pdf", "Indian Trusts Act", NOTES),
    ("INDIAN_SUCCESSION _ACT.pdf", "Indian Succession Act", NOTES),
    ("HINDU_LAW_2012.pdf", "Hindu Law", NOTES),
    ("MOHAMMADAN_LAW_ F.pdf", "Mohammedan Law", NOTES),
    ("LAW_OF_TORTS _F.pdf", "Law of Torts", NOTES),
    ("Kenny's_Criminal_Law.pdf", "Kenny's Criminal Law", NOTES),
    ("ADVOCATES_ACT_f.pdf", "Advocates Act", NOTES),
    ("ARBITRATION_And_CONCILIATION.pdf", "Arbitration and Conciliation Act", NOTES),
    ("ADMINISTRATIVE_LAW_FF.pdf", "Administrative Law", NOTES),
    ("LAW_OF_BANKING.pdf", "Law of Banking", NOTES),
    ("LAW_OF_INSURANCE_2012.pdf", "Law of Insurance", NOTES),
    ("JURISPRUDENCE_Legal_Theory_F.pdf", "Jurisprudence (Legal Theory)", NOTES),
    ("ANCIENT_LAW _F.pdf", "Ancient Indian Law", NOTES),
    ("INDIAN_LEGAL_HISTORY.pdf", "Indian Legal History", NOTES),
    ("INDIAN_CONSTITUTIONAL_HISTORY.pdf", "Indian Constitutional History", NOTES),
    ("LEGISLATIVE_DRAFTING.pdf", "Legislative Drafting", NOTES),
    ("PRINCIPLES_OF_LEGISLATION.pdf", "Principles of Legislation", NOTES),
    ("PUBLIC_INTERNATIONAL_LAW.pdf", "Public International Law", NOTES),
    ("U.N_CHARTER.pdf", "United Nations Charter", NOTES),
    ("Indian_Law_Reference_Catalog.pdf", "Indian Law Reference Catalog", "reference guide"),
]


def readable(data: bytes) -> bool:
    from io import BytesIO

    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(data))
        return len(reader.pages) > 0 and bool(reader.pages[0].extract_text() is not None)
    except Exception:  # noqa: BLE001 - any failure to open means it cannot be used
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--only", default="", help="add only sources whose title contains this text")
    parser.add_argument("--admin", default="admin@example.com", help="the administrator the sources are added as")
    args = parser.parse_args()

    settings = get_settings()
    settings.max_knowledge_pages = max(settings.max_knowledge_pages, 600)
    if ROOT in args.folder.resolve().parents:
        raise SystemExit("Keep the law PDFs outside the repository.")
    factory = sessionmaker(bind=get_engine(), expire_on_commit=False)

    seen: dict[str, str] = {}
    added = skipped = failed = 0
    with factory() as db:
        admin = db.scalar(select(User).where(User.email == args.admin, User.role == "admin"))
        if admin is None:
            raise SystemExit(f"No administrator {args.admin} in this database (run the seed command first).")
        for file_name, title, author in MANIFEST:
            if args.only and args.only.lower() not in title.lower():
                continue
            path = args.folder / file_name
            if not path.exists():
                print(f"  missing   {file_name}")
                failed += 1
                continue
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest in seen:
                print(f"  same file {file_name} (already added as {seen[digest]})")
                skipped += 1
                continue
            seen[digest] = title
            if not readable(data):
                print(f"  UNREADABLE {file_name}: the PDF is damaged or an incomplete download ({len(data)} bytes). Download it again.")
                failed += 1
                continue
            exists = db.scalar(
                select(func.count()).select_from(KnowledgeDocument).where(
                    func.lower(KnowledgeDocument.title) == title.lower(), KnowledgeDocument.owner_id.is_(None)
                )
            )
            if exists:
                print(f"  have      {title}")
                skipped += 1
                continue
            doc = knowledge.create_document(
                db, admin, title=title, citation=f"{title} ({author})", kind="act_section", text=None, file_name=file_name, data=data
            )
            db.commit()
            knowledge.process_document(factory, doc.id)
            db.refresh(doc)
            print(f"  {doc.status:9} {title}: {doc.page_count} pages, {doc.passage_count} passages" + (f" ({doc.status_reason})" if doc.status_reason else ""))
            added += doc.status == "ready"
            failed += doc.status != "ready"
    print(f"\nAdded {added}, skipped {skipped}, failed or missing {failed}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
