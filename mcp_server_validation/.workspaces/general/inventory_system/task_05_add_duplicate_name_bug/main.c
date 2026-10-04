#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#define MAX_ITEMS 100
#define NAME_LENGTH 64

typedef struct {
    char name[NAME_LENGTH];
    double price;
    int quantity;
} Item;

typedef struct {
    Item items[MAX_ITEMS];
    int count;
} Inventory;

void inventory_init(Inventory* inv) {
    inv->count = 0;
}

int inventory_find(const Inventory* inv, const char* name) {
    for (int i = 0; i < inv->count; ++i) {
        if (strcmp(inv->items[i].name, name) == 0) {
            return i;
        }
    }
    return -1;
}

// BUG: always appends a new entry, even when an item with the same name
// already exists, instead of merging quantity into the existing entry.
bool inventory_add(Inventory* inv, const char* name, double price, int quantity) {
    if (inv->count >= MAX_ITEMS) {
        return false;
    }
    Item* item = &inv->items[inv->count];
    strncpy(item->name, name, NAME_LENGTH - 1);
    item->name[NAME_LENGTH - 1] = '\0';
    item->price = price;
    item->quantity = quantity;
    inv->count++;
    return true;
}

bool inventory_remove(Inventory* inv, const char* name) {
    int index = inventory_find(inv, name);
    if (index < 0) {
        return false;
    }
    for (int i = index; i < inv->count - 1; ++i) {
        inv->items[i] = inv->items[i + 1];
    }
    inv->count--;
    return true;
}

double inventory_total_value(const Inventory* inv) {
    double total = 0.0;
    for (int i = 0; i < inv->count; ++i) {
        total += inv->items[i].price * inv->items[i].quantity;
    }
    return total;
}

int inventory_total_quantity(const Inventory* inv) {
    int total = 0;
    for (int i = 0; i < inv->count; ++i) {
        total += inv->items[i].quantity;
    }
    return total;
}

void inventory_sort_by_price(Inventory* inv) {
    for (int i = 0; i < inv->count - 1; ++i) {
        for (int j = 0; j < inv->count - 1 - i; ++j) {
            if (inv->items[j].price > inv->items[j + 1].price) {
                Item temp = inv->items[j];
                inv->items[j] = inv->items[j + 1];
                inv->items[j + 1] = temp;
            }
        }
    }
}

static int nearly_equal(double a, double b) {
    double diff = a - b;
    if (diff < 0) {
        diff = -diff;
    }
    return diff < 1e-9;
}

int test_add_new_item(void) {
    Inventory inv;
    inventory_init(&inv);
    bool added = inventory_add(&inv, "widget", 2.5, 10);
    return added && inv.count == 1;
}

int test_add_duplicate_merges_quantity(void) {
    Inventory inv;
    inventory_init(&inv);
    inventory_add(&inv, "widget", 2.5, 10);
    inventory_add(&inv, "widget", 2.5, 5);
    int index = inventory_find(&inv, "widget");
    return inv.count == 1 && index == 0 && inv.items[index].quantity == 15;
}

int test_add_duplicate_updates_price(void) {
    Inventory inv;
    inventory_init(&inv);
    inventory_add(&inv, "widget", 2.5, 10);
    inventory_add(&inv, "widget", 3.0, 5);
    int index = inventory_find(&inv, "widget");
    return nearly_equal(inv.items[index].price, 3.0);
}

int test_add_multiple_distinct_items(void) {
    Inventory inv;
    inventory_init(&inv);
    inventory_add(&inv, "a", 1.0, 1);
    inventory_add(&inv, "b", 2.0, 2);
    inventory_add(&inv, "a", 1.0, 3);
    return inv.count == 2 &&
           inv.items[inventory_find(&inv, "a")].quantity == 4 &&
           inv.items[inventory_find(&inv, "b")].quantity == 2;
}

int test_remove_after_merge(void) {
    Inventory inv;
    inventory_init(&inv);
    inventory_add(&inv, "widget", 2.5, 10);
    inventory_add(&inv, "widget", 2.5, 5);
    bool removed = inventory_remove(&inv, "widget");
    return removed && inv.count == 0;
}

int test_total_value_after_merge(void) {
    Inventory inv;
    inventory_init(&inv);
    inventory_add(&inv, "widget", 2.0, 10);
    inventory_add(&inv, "widget", 2.0, 5);
    return nearly_equal(inventory_total_value(&inv), 30.0);
}

int main(void) {
    struct Test {
        const char* name;
        int (*function)(void);
    };

    const struct Test tests[] = {
        {"add_new_item", test_add_new_item},
        {"add_duplicate_merges_quantity", test_add_duplicate_merges_quantity},
        {"add_duplicate_updates_price", test_add_duplicate_updates_price},
        {"add_multiple_distinct_items", test_add_multiple_distinct_items},
        {"remove_after_merge", test_remove_after_merge},
        {"total_value_after_merge", test_total_value_after_merge}
    };

    int failures = 0;
    for (size_t i = 0; i < sizeof(tests) / sizeof(tests[0]); ++i) {
        int passed = tests[i].function();
        if (passed) {
            printf("[PASS] %s\n", tests[i].name);
        } else {
            fprintf(stderr, "[FAIL] %s\n", tests[i].name);
            ++failures;
        }
    }

    if (failures > 0) {
        fprintf(stderr, "%d test(s) failed.\n", failures);
        return 1;
    }

    printf("All tests passed.\n");
    return 0;
}