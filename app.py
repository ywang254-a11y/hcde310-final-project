from flask import Flask, render_template, request
import urllib.parse
import urllib.request
import urllib.error
import json
import csv

app = Flask(__name__)

BASE_URL = "https://www.themealdb.com/api/json/v1/1"


def safe_get(url):
    try:
        api_request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )
        response = urllib.request.urlopen(api_request)
        response_str = response.read().decode("utf-8")
        return json.loads(response_str)

    except urllib.error.URLError as e:
        print("Error trying to retrieve data.")
        if hasattr(e, "reason"):
            print("Reason:", e.reason)
        elif hasattr(e, "code"):
            print("Error code:", e.code)
        return None


def get_meal_by_ingredient(ingredient):
    params = urllib.parse.urlencode({"i": ingredient})
    url = BASE_URL + "/filter.php?" + params

    data = safe_get(url)

    if data == None:
        return []

    if data["meals"] == None:
        return []

    return data["meals"]


def get_meal_details(meal_id):
    params = urllib.parse.urlencode({"i": meal_id})
    url = BASE_URL + "/lookup.php?" + params

    data = safe_get(url)

    if data == None:
        return None

    if data["meals"] == None:
        return None

    return data["meals"][0]


def load_price_data(filename):
    prices = {}

    with open(filename, "r") as f:
        reader = csv.DictReader(f)

        for row in reader:
            ingredient = row["ingredient"].lower().strip()
            price = float(row["price"])
            prices[ingredient] = price

    return prices


def extract_ingredients(meal):
    ingredients = []

    for i in range(1, 21):
        key = "strIngredient" + str(i)
        ingredient = meal.get(key)

        if ingredient != None and ingredient.strip() != "":
            ingredients.append(ingredient.lower().strip())

    return ingredients


def estimate_missing_cost(recipe_ingredients, user_ingredients, prices):
    missing_ingredients = []
    total_cost = 0

    for ingredient in recipe_ingredients:
        if ingredient not in user_ingredients:
            missing_ingredients.append(ingredient)

            if ingredient in prices:
                total_cost = total_cost + prices[ingredient]
            else:
                total_cost = total_cost + 1.5

    return missing_ingredients, total_cost


def calculate_practicality_score(recipe_ingredients, missing_ingredients, missing_cost, budget):
    if len(recipe_ingredients) == 0:
        return 1

    owned_count = len(recipe_ingredients) - len(missing_ingredients)
    ingredient_score = owned_count / len(recipe_ingredients) * 10

    if missing_cost <= budget:
        budget_score = 10
    else:
        budget_score = max(0, 10 - (missing_cost - budget))

    score = ingredient_score * 0.6 + budget_score * 0.4

    if score > 10:
        score = 10

    if score < 1:
        score = 1

    return round(score, 1)


def get_recommendations(user_ingredients, budget, meal_type):
    prices = load_price_data("ingredient_prices.csv")

    all_meals = {}

    for ingredient in user_ingredients:
        meals = get_meal_by_ingredient(ingredient)

        for meal in meals[:5]:
            meal_id = meal["idMeal"]
            all_meals[meal_id] = meal

    recommendations = []

    for meal_id in all_meals:
        full_meal = get_meal_details(meal_id)

        if full_meal != None:
            recipe_ingredients = extract_ingredients(full_meal)
            missing_ingredients, missing_cost = estimate_missing_cost(
                recipe_ingredients,
                user_ingredients,
                prices
            )

            score = calculate_practicality_score(
                recipe_ingredients,
                missing_ingredients,
                missing_cost,
                budget
            )

            recommendation = {
                "name": full_meal["strMeal"],
                "category": full_meal["strCategory"],
                "missing_ingredients": missing_ingredients,
                "missing_cost": round(missing_cost, 2),
                "score": score,
                "image": full_meal["strMealThumb"]
            }

            if meal_type == "No limitation" or recommendation["category"] == meal_type:
                recommendations.append(recommendation)

    recommendations.sort(key=lambda recipe: recipe["score"], reverse=True)

    return recommendations[:5]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/results", methods=["POST"])
def results():
    ingredients_input = request.form.get("ingredients")
    budget_input = request.form.get("budget")
    meal_type = request.form.get("meal_type")

    user_ingredients = []

    for ingredient in ingredients_input.split(","):
        cleaned_ingredient = ingredient.lower().strip()

        if cleaned_ingredient != "":
            user_ingredients.append(cleaned_ingredient)

    budget = float(budget_input)

    recommendations = get_recommendations(user_ingredients, budget, meal_type)

    return render_template(
        "results.html",
        user_ingredients=user_ingredients,
        budget=budget,
        meal_type=meal_type,
        recommendations=recommendations
    )


if __name__ == "__main__":
    app.run(debug=True)
    