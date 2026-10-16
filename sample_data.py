"""Fictional leads and conversations, dated relative to first launch."""
from datetime import timedelta
REPS = ['Asha', 'Rohan', 'Meera', 'Vikram', 'Neha']
SCENARIOS = [
 ('Aarav Shah', 'FreshBox Foods', 4, 'Please send a quotation for a pouch packing machine. We need it urgently.'),
 ('Diya Patel', 'GreenLeaf Tea', 1, 'Can we schedule a demo today? We pack 200g tea pouches.'),
 ('Kabir Rao', 'SpiceRoute Foods', 7, 'We are ready to buy. What do you need for the purchase order?'),
 ('Ananya Iyer', 'PureDrop Water', 2, 'We are comparing suppliers. Can you share pricing?'),
 ('Arjun Das', 'NutriPack', 5, 'We have budget approval. Please send a quote.'),
 ('Ishita Jain', 'HerbalNest', 1, 'Please follow up next month. Budget is still pending.'),
 ('Vihaan Nair', 'CrispBite Snacks', 8, 'Interested, but we need to hold until the budget review.'),
 ('Saanvi Roy', 'DairyDay', 2, 'Can your equipment handle 500g packs? We are exploring options.'),
 ('Reyansh Mehta', 'GoodGrain', 3, 'We pack flour in 1kg bags. Happy to discuss our requirements.'),
 ('Myra Kapoor', 'Bloom Cosmetics', 28, 'Thanks for the catalogue. We will review it.'),
 ('Advik Singh', 'Metro Staples', 35, 'Received, thank you.'),
 ('Kiara Verma', 'DailyHarvest', 2, 'Not interested. Please do not contact us again.'),
 ('Ayaan Gupta', 'Sunrise Bakery', 1, 'Please schedule a demo tomorrow.'),
 ('Pari Joshi', 'OceanSalt', 10, 'Please check in next week after our production meeting.'),
 ('Rudra Bose', 'EcoWrap', 6, 'We want to place an order. Can we discuss configuration?'),
 ('Tara Menon', 'GoldenBeans', 22, 'We already purchased from another vendor.'),
 ('Vivaan Sethi', 'PouchCraft', 1, 'Please share pricing for the sealing machine.'),
 ('Avni Kulkarni', 'FarmPure', 12, 'The budget is delayed. Please call next quarter.'),
 ('Dhruv Reddy', 'SnackLab', 5, 'Could you explain the available packing formats?'),
 ('Nisha Bhat', 'WellnessRoots', 40, 'I will get back to you.'),
 ('Om Desai', 'QuickPack', 3, 'We need a demo for our new production line.'),
 ('Riya Sen', 'ChocoCraft', 1, 'We need to discuss requirements with our operations team.'),
 ('Yash Malhotra', 'HarvestHub', 18, 'Budget is pending; can you check later?'),
 ('Sara Ali', 'PetMeal', 30, 'Thanks for reaching out.'),
 ('Dev Arora', 'UrbanGrind', 2, 'Please send a quotation for coffee pouch packaging.'),
]


def records(current):
    for i, (name, company, days, reply) in enumerate(SCENARIOS):
        contact = (current - timedelta(days=days)).isoformat()
        yield {'name': name, 'company': company, 'phone': f'+91 00000 {i:05d}',
               'source': ['Excel', 'WhatsApp', 'Referral', 'Website'][i % 4],
               'rep': REPS[i % 5], 'last_contact': contact}, [
            {'sender': 'Rep', 'body': f'Hi {name.split()[0]}, thanks for your interest in our packaging equipment. What does {company} need?', 'created_at': contact + 'T10:00:00'},
            {'sender': 'Buyer', 'body': reply, 'created_at': contact + 'T10:05:00'}]
