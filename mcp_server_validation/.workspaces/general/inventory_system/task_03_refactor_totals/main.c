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

// DUPLICATION: both functions below repeat the same "loop over inv->items,
// accumulate a per-item numeric value" structure, differing only in what
// gets accumulated (price*quantity vs quantity).
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

int test_add_and_find(void) {
    Inventory inv;
    inventory_init(&inv);
    inventory_add(&inv, "widget", 2.5, 10);
    return inventory_find(&inv, "widget") == 0;
}

int test_remove(void) {
    Inventory inv;
    inventory_init(&inv);
    inventory_add(&inv, "a", 1.0, 1);
    inventory_add(&inv, "b", 2.0, 2);
    bool removed = inventory_remove(&inv, "a");
    return removed && inv.count == 1;
}

int test_total_value_basic(void) {
    Inventory inv;
    inventory_init(&inv);
    inventory_add(&inv, "a", 2.0, 3);
    inventory_add(&inv, "b", 5.0, 1);
    return nearly_equal(inventory_total_value(&inv), 11.0);
}

int test_total_value_empty(void) {
    Inventory inv;
    inventory_init(&inv);
    return nearly_equal(inventory_total_value(&inv), 0.0);
}

int test_total_quantity_basic(void) {
    Inventory inv;
    inventory_init(&inv);
    inventory_add(&inv, "a", 2.0, 3);
    inventory_add(&inv, "b", 5.0, 7);
    return inventory_total_quantity(&inv) == 10;
}

int test_total_quantity_empty(void) {
    Inventory inv;
    inventory_init(&inv);
    return inventory_total_quantity(&inv) == 0;
}

int test_sort_by_price(void) {
    Inventory inv;
    inventory_init(&inv);
    inventory_add(&inv, "mid", 5.0, 1);
    inventory_add(&inv, "low", 1.0, 1);
    inventory_add(&inv, "high", 9.0, 1);
    inventory_sort_by_price(&inv);
    return strcmp(inv.items[0].name, "low") == 0 &&
           strcmp(inv.items[2].name, "high") == 0;
}

int main(void) {
    struct Test {
        const char* name;
        int (*function)(void);
    };

    const struct Test tests[] = {
        {"add_and_find", test_add_and_find},
        {"remove", test_remove},
        {"total_value_basic", test_total_value_basic},
        {"total_value_empty", test_total_value_empty},
        {"total_quantity_basic", test_total_quantity_basic},
        {"total_quantity_empty", test_total_quantity_empty},
        {"sort_by_price", test_sort_by_price}
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