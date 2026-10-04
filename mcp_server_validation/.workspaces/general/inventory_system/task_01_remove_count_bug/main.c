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

// BUG: shifts elements to fill the gap correctly, but never decrements
// inv->count, so the (now duplicated) last slot is still considered valid.
bool inventory_remove(Inventory* inv, const char* name) {
    int index = inventory_find(inv, name);
    if (index < 0) {
        return false;
    }
    for (int i = index; i < inv->count - 1; ++i) {
        inv->items[i] = inv->items[i + 1];
    }
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

int test_add_and_find(void) {
    Inventory inv;
    inventory_init(&inv);
    inventory_add(&inv, "widget", 2.5, 10);
    inventory_add(&inv, "gadget", 5.0, 4);
    return inventory_find(&inv, "gadget") == 1 && inventory_find(&inv, "missing") == -1;
}

int test_remove_middle(void) {
    Inventory inv;
    inventory_init(&inv);
    inventory_add(&inv, "a", 1.0, 1);
    inventory_add(&inv, "b", 2.0, 2);
    inventory_add(&inv, "c", 3.0, 3);
    bool removed = inventory_remove(&inv, "b");
    return removed &&
           inv.count == 2 &&
           inventory_find(&inv, "b") == -1 &&
           inventory_find(&inv, "a") == 0 &&
           inventory_find(&inv, "c") == 1;
}

int test_remove_updates_totals(void) {
    Inventory inv;
    inventory_init(&inv);
    inventory_add(&inv, "a", 1.0, 1);
    inventory_add(&inv, "b", 2.0, 2);
    inventory_add(&inv, "c", 3.0, 3);
    inventory_remove(&inv, "b");
    return nearly_equal(inventory_total_value(&inv), 10.0) &&
           inventory_total_quantity(&inv) == 4;
}

int test_remove_last(void) {
    Inventory inv;
    inventory_init(&inv);
    inventory_add(&inv, "only", 9.0, 1);
    bool removed = inventory_remove(&inv, "only");
    return removed && inv.count == 0;
}

int test_remove_not_found(void) {
    Inventory inv;
    inventory_init(&inv);
    inventory_add(&inv, "a", 1.0, 1);
    bool removed = inventory_remove(&inv, "nope");
    return !removed && inv.count == 1;
}

int test_sort_by_price(void) {
    Inventory inv;
    inventory_init(&inv);
    inventory_add(&inv, "mid", 5.0, 1);
    inventory_add(&inv, "low", 1.0, 1);
    inventory_add(&inv, "high", 9.0, 1);
    inventory_sort_by_price(&inv);
    return strcmp(inv.items[0].name, "low") == 0 &&
           strcmp(inv.items[1].name, "mid") == 0 &&
           strcmp(inv.items[2].name, "high") == 0;
}

int main(void) {
    struct Test {
        const char* name;
        int (*function)(void);
    };

    const struct Test tests[] = {
        {"add_and_find", test_add_and_find},
        {"remove_middle", test_remove_middle},
        {"remove_updates_totals", test_remove_updates_totals},
        {"remove_last", test_remove_last},
        {"remove_not_found", test_remove_not_found},
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