# Invoice totals

A command-line tool for an accountant to total invoices in a CSV file.
Each row contains a customer and a decimal amount. The tool prints totals by
customer as JSON. It runs locally without a network service or language model.

Run `python main.py invoices.csv`. Invalid numeric amounts stop the command;
there is no automatic repair or web interface.
