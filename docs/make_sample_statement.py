"""Generate docs/sample-statement-starling.csv: an invented sole trader's 18-month statement for testing."""
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)
rows = ["Date,Counter Party,Reference,Type,Amount (GBP),Balance (GBP),Spending Category,Notes"]
bal, d, end, events = 6200.0, date(2025, 4, 6), date(2026, 10, 16), []
while d <= end:
    season = 0.6 if d.month in (12, 1, 2) else 1.1
    if d.weekday() < 5 and random.random() < 0.07 * season:
        who = random.choice(["Mrs J Patel", "R Okafor", "Mr & Mrs Hughes", "S Kowalski", "The Oak Cafe", "A Brennan"])
        events.append((d, who, "Electrical work", round(random.lognormvariate(6.9, 0.5), 2)))
    if d.day == 3 and random.random() < 0.75:
        events.append((d + timedelta(days=random.randint(0, 4)), "Hartley Builders Ltd", f"INV {random.randint(1000, 1999)}", round(random.uniform(1500, 2700), 2)))
    if d.day == 17 and random.random() < 0.5:
        events.append((d, "Kemp Construction", f"INV {random.randint(2000, 2999)}", round(random.uniform(1500, 2800), 2)))
    if d.weekday() == 1 and random.random() < 0.6:
        events.append((d, random.choice(["Screwfix", "Toolstation", "CEF Electrical", "Edmundson Electrical"]), "Card", -round(random.uniform(40, 420), 2)))
    if d.day == 7:
        events += [(d, "Admiral Van Insurance", "DD", -96.00), (d, "EE Limited", "DD", -38.00), (d, "Shell", "Card", -round(random.uniform(150, 260), 2))]
    if d.day == 28:
        events.append((d, "D Smith", "Transfer to personal account", -2600.00))
    if d.day == 12 and random.random() < 0.5:
        events.append((d, "Tesco Stores", "Card", -round(random.uniform(20, 80), 2)))
    d += timedelta(days=1)
events += [(date(2026, 1, 31), "HMRC Self Assessment", "1234567890K", -6840.00),
           (date(2026, 7, 31), "HMRC Self Assessment", "1234567890K", -4420.00)]
for day, who, ref, amt in sorted(events, key=lambda e: e[0]):
    bal += amt
    rows.append(f"{day:%d/%m/%Y},{who},{ref},FASTER PAYMENT,{amt:.2f},{bal:.2f},{'INCOME' if amt > 0 else 'GENERAL'},")
Path(__file__).with_name("sample-statement-starling.csv").write_text("\n".join(rows) + "\n")
print(len(rows) - 1, "rows, closing balance", round(bal, 2))
