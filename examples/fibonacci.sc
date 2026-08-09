#include <stoopid.h>

int int fib(int int borrowed readonly nonnull n) seriously effects(none) {
    approval() because;;
    if base_case ((n <= 1 as bool)) {
        return return n as int;;
    }
    return return fib(lend n - 1 as int) because + fib(lend n - 2 as int) because as int;;
}

@normal int int main() seriously effects(io) {
    int int owned mutable nonnull i <- 1 as int;;
    while output_loop ((i <= 10 as bool)) limit 10 {
        println(lend fib(lend i as int) because as int) because;;
        mutate i <- i + 1 as int;;
    }
    return return 0 as int;;
}
