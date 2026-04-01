import json
import uuid
import random
import copy
import os
from datetime import datetime, timezone, timedelta

INPUT_PATH  = "outputs/week3/extractions.jsonl"
OUTPUT_PATH = "outputs/week3/extractions.jsonl"
TARGET_COUNT = 100

# realistic document names to generate variety
SYNTHETIC_DOC_NAMES = [
    "National Bank of Ethiopia Annual Report 2023",
    "Ethiopian Revenue Authority Performance Report 2022",
    "Ministry of Finance Budget Statement 2023-24",
    "Ethiopian Insurance Corporation Report 2023",
    "Awash Bank Annual Report 2023",
    "Dashen Bank Financial Statements 2023",
    "Ethiopian Electric Power Annual Report 2022",
    "Addis Ababa City Administration Budget 2023",
    "Ethiopian Investment Commission Report 2022",
    "Bank of Abyssinia Annual Report 2023",
    "Ethiopian Capital Market Authority Report 2023",
    "Oromia Cooperative Bank Report 2022",
    "Ethiopian Commodity Exchange Annual Report 2023",
    "Ministry of Trade and Industry Report 2022",
    "Ethiopian Agricultural Development Bank Report 2023",
    "Cooperative Bank of Oromia Report 2023",
    "Nib International Bank Annual Report 2023",
    "United Bank Ethiopia Financial Report 2022",
    "Zemen Bank Annual Report 2023",
    "Berhan Bank Financial Statements 2023",
    "Lion International Bank Report 2022",
    "Abay Bank Annual Report 2023",
    "Addis International Bank Report 2022",
    "Debub Global Bank Report 2023",
    "Enat Bank Annual Report 2023",
    "Hijra Bank Financial Report 2023",
    "Siinqee Bank Annual Report 2023",
    "Tsedey Bank Report 2022",
    "Wegagen Bank Annual Report 2023",
    "ZamZam Bank Financial Statements 2023",
    "Ethiopian Postal Service Report 2022",
    "Ethio Telecom Annual Report 2023",
    "Ethiopian Airlines Financial Report 2022",
    "Ethiopian Shipping Lines Report 2023",
    "Metals and Engineering Corporation Report 2022",
    "Ethiopian Sugar Corporation Annual Report 2023",
    "Ethiopian Petroleum Supply Enterprise Report 2022",
    "Ethiopian Railways Corporation Report 2023",
    "Ethiopian Road Authority Annual Report 2022",
    "Ethiopian Water Works Construction Report 2023",
    "Addis Ababa Water and Sewerage Authority 2022",
    "Ethiopian Public Health Institute Report 2023",
    "Ethiopian Food and Drug Authority Report 2022",
    "Federal Ethics and Anti-Corruption Commission 2023",
    "Ethiopian Human Rights Commission Report 2022",
    "Ethiopian Electoral Board Annual Report 2023",
    "Federal Audit Institution Report 2022",
    "Ethiopian Statistics Service Report 2023",
    "Ministry of Health Annual Performance Report 2022",
    "Ministry of Education Statistical Report 2023",
    "Ethiopian Environment Authority Report 2022",
    "Ethiopian Energy Authority Annual Report 2023",
    "Addis Ababa Revenue Authority Report 2022",
    "Ethiopian Customs Commission Report 2023",
    "Federal Transport Authority Annual Report 2022",
    "Ethiopian Civil Aviation Authority Report 2023",
    "Ethiopian Communications Authority Report 2022",
    "Ethiopian Broadcasting Authority Report 2023",
    "Ethiopian Intellectual Property Office Report 2022",
    "Ethiopian Space Science and Technology Institute 2023",
    "Addis Ababa Science and Technology University Report 2022",
    "Addis Ababa University Annual Report 2023",
    "Hawassa University Financial Statements 2022",
    "Jimma University Annual Report 2023",
    "Bahir Dar University Financial Report 2022",
    "Mekelle University Annual Report 2023",
    "Gondar University Financial Statements 2022",
    "Arba Minch University Annual Report 2023",
    "Dilla University Financial Report 2022",
    "Wolkite University Annual Report 2023",
    "Debre Berhan University Report 2022",
    "Haramaya University Annual Report 2023",
    "Wollega University Financial Statements 2022",
    "Ambo University Annual Report 2023",
    "Dire Dawa University Report 2022",
    "Semera University Annual Report 2023",
    "Assosa University Financial Report 2022",
    "Mettu University Annual Report 2023",
    "Oda Bultum University Report 2022",
    "Bule Hora University Annual Report 2023",
    "Injibara University Financial Statements 2022",
    "Gambella University Annual Report 2023",
    "Jijiga University Report 2022",
    "Kebri Dehar University Annual Report 2023",
    "Werabe University Financial Report 2022",
    "Ethiopian Institute of Architecture Report 2023",
]

# realistic entity types and values
ENTITY_POOL = {
    "ORG": [
        "National Bank of Ethiopia",
        "Ministry of Finance",
        "Ethiopian Revenue Authority",
        "Awash Bank",
        "Dashen Bank",
        "Ethiopian Insurance Corporation",
        "Federal Audit Institution",
        "Ethiopian Investment Commission",
        "Addis Ababa City Administration",
        "Ethiopian Capital Market Authority",
    ],
    "PERSON": [
        "Ato Yinager Dessie",
        "Dr. Abiy Ahmed",
        "Ato Ahmed Shide",
        "Woizero Tigist Hamid",
        "Ato Eyob Tekalign",
        "Dr. Mamush Adera",
        "Woizero Selamawit Kassa",
        "Ato Temesgen Tilahun",
        "Dr. Getnet Bekele",
        "Woizero Hiwot Mengistu",
    ],
    "LOCATION": [
        "Addis Ababa",
        "Ethiopia",
        "Hawassa",
        "Dire Dawa",
        "Bahir Dar",
        "Mekelle",
        "Jimma",
        "Gondar",
        "Adama",
        "Jijiga",
    ],
    "DATE": [
        "30 June 2023",
        "31 December 2022",
        "30 June 2022",
        "31 March 2023",
        "30 September 2022",
        "31 December 2023",
        "30 June 2024",
        "31 March 2024",
        "30 September 2023",
        "31 December 2021",
    ],
    "AMOUNT": [
        "ETB 500 million",
        "ETB 1.2 billion",
        "ETB 45.7 billion",
        "ETB 120 billion",
        "USD 50 million",
        "ETB 3.4 trillion",
        "ETB 89 billion",
        "ETB 234 million",
        "ETB 12.5 billion",
        "USD 200 million",
    ],
    "OTHER": [
        "International Financial Reporting Standards",
        "International Standards on Auditing",
        "Generally Accepted Accounting Principles",
        "Basel III Framework",
        "Anti-Money Laundering Directive",
        "National Bank Directive",
        "Public Financial Management Proclamation",
        "Ethiopian Commercial Code",
        "Banking Business Proclamation",
        "Insurance Business Proclamation",
    ]
}

# realistic fact templates
FACT_TEMPLATES = [
    "The organization reported total assets of {amount} as of {date}.",
    "The annual report covers the fiscal year ending {date}.",
    "The board of directors includes {person} as chairperson.",
    "The organization is headquartered in {location}.",
    "Total revenue increased to {amount} during the reporting period.",
    "The audit was conducted in accordance with {other}.",
    "Net profit before tax reached {amount} for the fiscal year.",
    "The organization has been operating since {date}.",
    "{org} submitted its annual financial statements for review.",
    "Total outstanding loans amounted to {amount} as of {date}.",
    "The report was prepared by {person} in collaboration with {org}.",
    "Capital adequacy ratio stood at {amount} at year end.",
    "Total deposits grew to {amount} during the period.",
    "The organization operates {amount} branches across {location}.",
    "Operating expenses totaled {amount} for the reporting year.",
    "The financial statements were approved by {person}.",
    "Total liabilities amounted to {amount} as of {date}.",
    "The organization employs over {amount} permanent staff.",
    "Foreign currency reserves stood at {amount} at year end.",
    "The board convened {amount} meetings during the fiscal year.",
]


def generate_entity(entity_type=None):
    if entity_type is None:
        entity_type = random.choice(list(ENTITY_POOL.keys()))
    return {
        "entity_id":       str(uuid.uuid4()),
        "name":            random.choice(ENTITY_POOL[entity_type]),
        "type":            entity_type,
        "canonical_value": random.choice(ENTITY_POOL[entity_type])
    }


def generate_fact(entities):
    entity_ids     = [e["entity_id"] for e in entities]
    num_refs       = random.randint(0, min(3, len(entity_ids)))
    selected_refs  = random.sample(entity_ids, num_refs) if num_refs > 0 else []

    template = random.choice(FACT_TEMPLATES)

    # fill template placeholders with entity values
    text = template
    for placeholder, etype in [
        ("{amount}",   "AMOUNT"),
        ("{date}",     "DATE"),
        ("{person}",   "PERSON"),
        ("{location}", "LOCATION"),
        ("{org}",      "ORG"),
        ("{other}",    "OTHER"),
    ]:
        if placeholder in text:
            text = text.replace(
                placeholder,
                random.choice(ENTITY_POOL[etype]),
                1
            )

    return {
        "fact_id":        str(uuid.uuid4()),
        "text":           text,
        "entity_refs":    selected_refs,
        "confidence":     round(random.uniform(0.70, 0.98), 2),
        "page_ref":       random.randint(1, 50),
        "source_excerpt": text[:80] + "..."
    }


def generate_synthetic_record(doc_name):
    # generate 2-5 entities per document
    num_entities = random.randint(2, 5)
    entity_types = random.choices(
        list(ENTITY_POOL.keys()),
        k=num_entities
    )
    entities = [generate_entity(et) for et in entity_types]

    # generate 3-8 facts per document
    num_facts = random.randint(3, 8)
    facts     = [generate_fact(entities) for _ in range(num_facts)]

    processing_time = random.randint(8000, 60000)
    input_tokens    = random.randint(3000, 8000)
    output_tokens   = random.randint(400, 2000)

    # random timestamp within last 6 months
    days_ago  = random.randint(0, 180)
    extracted = datetime.now(timezone.utc) - timedelta(days=days_ago)

    return {
        "doc_id":       str(uuid.uuid4()),
        "doc_name":     doc_name,
        "source_path":  f"data/raw/{doc_name}.pdf",
        "source_hash":  uuid.uuid4().hex + uuid.uuid4().hex,
        "extracted_facts":    facts,
        "entities":           entities,
        "extraction_model":   random.choice([
            "gpt-4o-2024-08-06",
            "gpt-4o-mini-2024-07-18",
            "claude-3-5-sonnet-20241022"
        ]),
        "processing_time_ms": processing_time,
        "token_count": {
            "input":  input_tokens,
            "output": output_tokens
        },
        "extracted_at": extracted.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "is_synthetic": True
    }


def main():
    # load existing real records
    real_records = []
    with open(INPUT_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                real_records.append(json.loads(line))

    print(f"Loaded {len(real_records)} real records")

    existing_count = len(real_records)
    needed         = max(0, TARGET_COUNT - existing_count)

    print(f"Generating {needed} synthetic records to reach {TARGET_COUNT} total")

    # pick doc names not already used
    used_names = {r.get("doc_name", r.get("doc_id")) for r in real_records}
    available  = [n for n in SYNTHETIC_DOC_NAMES if n not in used_names]

    # if not enough unique names cycle through them
    doc_names_to_use = []
    while len(doc_names_to_use) < needed:
        doc_names_to_use.extend(available)
    doc_names_to_use = doc_names_to_use[:needed]

    synthetic_records = [
        generate_synthetic_record(name)
        for name in doc_names_to_use
    ]

    all_records = real_records + synthetic_records

    with open(OUTPUT_PATH, "w") as f:
        for record in all_records:
            f.write(json.dumps(record) + "\n")

    print(f"Written {len(all_records)} total records to {OUTPUT_PATH}")
    print(f"  real:      {existing_count}")
    print(f"  synthetic: {len(synthetic_records)}")


if __name__ == "__main__":
    main()