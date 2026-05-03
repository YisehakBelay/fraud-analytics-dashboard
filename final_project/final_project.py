from pymongo import MongoClient
import json

client = MongoClient("mongodb://localhost:27017/")
db = client["finals_database_project"]
transactions = db["transactions_data"]
users = db["user_data"]
cards = db["cards_data"]

#1.	Compare client (age/retirement/income) and average transaction amount


#2.	Compare card (type/brand/credit limit) and average transaction amount


#3.	List top 10 states by (total/average) transaction amount


#4.	List top 10 states by transaction count


#5.	Compare chip, swipe, and online transactions by count/total/average


#6.	Cards with >80% spend in a year than its per capita income
pipeline_totals = [
    { "$addFields": { "amountNum": { "$toDouble": { "$substr": ["$amount", 1, -1] } } }},
    { "$group": {
        "_id": {
            "card":      "$card_id",
            "client_id": "$client_id",
            "year":      { "$year": { "$dateFromString": { "dateString": "$date", "format": "%Y-%m-%d %H:%M:%S" } } }
        },
        "totalSpent": { "$sum": "$amountNum" }
    }}
]

print("Running aggregation on 13M records, this will take a while...")
totals = list(transactions.aggregate(pipeline_totals))
print(f"Got {len(totals)} card/year combinations")

user_lookup = {
    u["id"]: { "address": u["address"], "pci": float(u["per_capita_income"].replace("$", "").replace(",", "")) }
    for u in users.find({}, { "id": 1, "address": 1, "per_capita_income": 1 })
}
print(f"Loaded {len(user_lookup)} users")

results = []
for doc in totals:
    client_id = doc["_id"]["client_id"]
    user = user_lookup.get(client_id)
    if user and doc["totalSpent"] > user["pci"] * 0.80:
        results.append({
            "address":  user["address"],
            "card_id":  doc["_id"]["card"],
            "year":     doc["_id"]["year"],
            "totalSpent": round(doc["totalSpent"], 2),
            "PCI":      user["pci"]
        })

with open("high_spenders.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Exported {len(results)} records to high_spenders.json")

#7.	Swiped cards in a different state than the persons home state.
query7 = [
    { "$addFields": {
        "amountNum": { "$toDouble": { "$substr": ["$amount", 1, -1] } },
        "hour": { "$hour": { "$dateFromString": { "dateString": "$date", "format": "%Y-%m-%d %H:%M:%S" } } }
    }},
    { "$addFields": {
        "timeOfDay": { "$cond": {
            "if":   { "$or": [ { "$gte": ["$hour", 22] }, { "$lt": ["$hour", 6] } ] },
            "then": "night",
            "else": "day"
        }}
    }},
    { "$group": {
        "_id":          "$timeOfDay",
        "count":        { "$sum": 1 },
        "totalAmount":  { "$sum": "$amountNum" },
        "avgAmount":    { "$avg": "$amountNum" }
    }},
    { "$project": {
        "_id":         0,
        "timeOfDay":   "$_id",
        "count":       1,
        "totalAmount": { "$round": ["$totalAmount", 2] },
        "avgAmount":   { "$round": ["$avgAmount", 2] }
    }}
]

print("Running query 7...")
results7 = list(transactions.aggregate(query7))
print(f"Results: {results7}")

with open("day_vs_night.json", "w") as f:
    json.dump(results7, f, indent=2)

print("Exported to day_vs_night.json")

#8.	Find cards/users with >1 error
query8 = [
    { "$match": { "errors": { "$exists": True } } },
    { "$group": {
        "_id": "$card_id",
        "errorCount": { "$sum": 1 },
        "errors":     { "$push": "$errors" },
        "client_id":  { "$first": "$client_id" }
    }},
    { "$match": { "errorCount": { "$gt": 1 } } },
    { "$lookup": { "from": "user_data", "localField": "client_id", "foreignField": "id", "as": "customer" } },
    { "$unwind": "$customer" },
    { "$project": {
        "_id":        0,
        "card_id":    "$_id",
        "address":    "$customer.address",
        "errorCount": 1,
        "errors":     1
    }}
]

print("Running query 8...")
results = list(transactions.aggregate(query8))
print(f"Found {len(results)} cards with more than 1 error")

with open("error_cards.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"Exported {len(results)} records to error_cards.json")

#9.	Amount of transactions with a negative amount ordered by state
query9 = [
    { "$addFields": { "amountNum": { "$toDouble": { "$substr": ["$amount", 1, -1] } } }},
    { "$match": { "amountNum": { "$lt": 0 } } },
    { "$group": {
        "_id":   "$merchant_state",
        "count": { "$sum": 1 }
    }},
    { "$sort": { "count": -1 } },
    { "$project": {
        "_id":   0,
        "state": "$_id",
        "count": 1
    }}
]

print("Running query 9...")
results9 = list(transactions.aggregate(query9))
print(f"Found {len(results9)} states with negative transactions")

with open("negative_transactions_by_state.json", "w") as f:
    json.dump(results9, f, indent=2)

print("Exported to negative_transactions_by_state.json")

#10.Percentage of cards with 2 cards issued that overdrew they credit limit more than twice vs the amount of single issued cards.
print("Loading cards...")
card_lookup = {}
for c in cards.find({}, { "id": 1, "credit_limit": 1, "num_cards_issued": 1 }):
    card_lookup[c["id"]] = {
        "credit_limit":     float(c["credit_limit"].replace("$", "").replace(",", "")),
        "num_cards_issued": c["num_cards_issued"]
    }
print(f"Loaded {len(card_lookup)} cards")

print("Running aggregation on transactions...")
pipeline = [
    { "$addFields": { "amountNum": { "$toDouble": { "$substr": ["$amount", 1, -1] } } }},
    { "$group": {
        "_id":          "$card_id",
        "transactions": { "$push": "$amountNum" }
    }}
]

totals = list(transactions.aggregate(pipeline))
print(f"Got {len(totals)} cards")

single_total    = 0
single_overdrew = 0
double_total    = 0
double_overdrew = 0

for doc in totals:
    card = card_lookup.get(doc["_id"])
    if not card:
        continue

    overdraw_count = sum(1 for a in doc["transactions"] if a > card["credit_limit"])
    num_issued     = card["num_cards_issued"]

    if num_issued == 1:
        single_total += 1
        if overdraw_count > 2:
            single_overdrew += 1
    elif num_issued == 2:
        double_total += 1
        if overdraw_count > 2:
            double_overdrew += 1

results10 = [
    {
        "num_cards_issued": 1,
        "total":            single_total,
        "overdrew":         single_overdrew,
        "percentage":       round(single_overdrew / single_total * 100, 2) if single_total > 0 else 0
    },
    {
        "num_cards_issued": 2,
        "total":            double_total,
        "overdrew":         double_overdrew,
        "percentage":       round(double_overdrew / double_total * 100, 2) if double_total > 0 else 0
    }
]

with open("overdraw_percentage.json", "w") as f:
    json.dump(results10, f, indent=2)

print(f"Results: {results10}")
print("Exported to overdraw_percentage.json")



import json

# ---------------- Q1 ----------------
print("Running Q1...")

pipeline1 = [
    {"$lookup": {
        "from": "cards_data",
        "localField": "card_id",
        "foreignField": "id",
        "as": "card"
    }},
    {"$unwind": "$card"},
    {"$lookup": {
        "from": "users_data",
        "localField": "card.client_id",
        "foreignField": "id",
        "as": "user"
    }},
    {"$unwind": "$user"},
    {"$group": {
        "_id": {
            "age": "$user.age",
            "retirement": "$user.retirement",
            "income": "$user.income"
        },
        "avgTransaction": {"$avg": "$amount"}
    }}
]

result1 = list(db.transactions_data.aggregate(pipeline1))

with open("demographics_avg_transaction.json", "w") as f:
    json.dump(result1, f, indent=4)

print("Q1 done")


# ---------------- Q2 ----------------
print("Running Q2...")

pipeline2 = [
    {"$lookup": {
        "from": "cards_data",
        "localField": "card_id",
        "foreignField": "id",
        "as": "card"
    }},
    {"$unwind": "$card"},
    {"$group": {
        "_id": {
            "type": "$card.type",
            "brand": "$card.brand",
            "credit_limit": "$card.credit_limit"
        },
        "avgTransaction": {"$avg": "$amount"}
    }}
]

result2 = list(db.transactions_data.aggregate(pipeline2))

with open("card_type_avg_transaction.json", "w") as f:
    json.dump(result2, f, indent=4)

print("Q2 done")


# ---------------- Q3 ----------------
print("Running Q3...")

pipeline3 = [
    {"$lookup": {
        "from": "users_data",
        "localField": "user_id",
        "foreignField": "id",
        "as": "user"
    }},
    {"$unwind": "$user"},
    {"$group": {
        "_id": "$user.state",
        "totalAmount": {"$sum": "$amount"},
        "avgAmount": {"$avg": "$amount"}
    }},
    {"$sort": {"totalAmount": -1}},
    {"$limit": 10}
]

result3 = list(db.transactions_data.aggregate(pipeline3))

with open("top_states_amount.json", "w") as f:
    json.dump(result3, f, indent=4)

print("Q3 done")


# ---------------- Q4 ----------------
print("Running Q4...")

pipeline4 = [
    {"$lookup": {
        "from": "users_data",
        "localField": "user_id",
        "foreignField": "id",
        "as": "user"
    }},
    {"$unwind": "$user"},
    {"$group": {
        "_id": "$user.state",
        "transactionCount": {"$sum": 1}
    }},
    {"$sort": {"transactionCount": -1}},
    {"$limit": 10}
]

result4 = list(db.transactions_data.aggregate(pipeline4))

with open("top_states_count.json", "w") as f:
    json.dump(result4, f, indent=4)

print("Q4 done")


# ---------------- Q5 ----------------
print("Running Q5...")

pipeline5 = [
    {"$group": {
        "_id": "$transaction_type",
        "totalAmount": {"$sum": "$amount"},
        "avgAmount": {"$avg": "$amount"},
        "count": {"$sum": 1}
    }}
]

result5 = list(db.transactions_data.aggregate(pipeline5))

with open("transaction_type_comparison.json", "w") as f:
    json.dump(result5, f, indent=4)

print("Q5 done")