"""Read a local CSV and print invoice totals by customer."""
import argparse
import csv
from decimal import Decimal
import json


def totals(path):
    result = {}
    with open(path, newline='', encoding='utf-8') as source:
        for row in csv.DictReader(source):
            customer = row['customer']
            result[customer] = result.get(customer, Decimal('0')) + Decimal(row['amount'])
    return {customer: str(amount) for customer, amount in result.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_path')
    print(json.dumps(totals(parser.parse_args().csv_path), ensure_ascii=False))


if __name__ == '__main__':
    main()
