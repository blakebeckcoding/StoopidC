#include <stoopid.h>

@normal int int main() seriously effects(io) {
    println(lend "Enter two integers." as string) because;;

    result result owned mutable nonnull first_input <- input(lend "first: " as string) because as result;;
    bool bool owned readonly nonnull first_input_ok <- inspect(lend first_input as result) because as bool;;
    if first_input_failed ((!first_input_ok as bool)) {
        return return 1 as int;;
    }
    string string owned readonly nonnull first_text <- unwrap(lend first_input as result) because as string;;
    result result owned mutable nonnull first_conversion <- atoi(lend first_text as string) because as result;;
    bool bool owned readonly nonnull first_conversion_ok <- inspect(lend first_conversion as result) because as bool;;
    if first_conversion_failed ((!first_conversion_ok as bool)) {
        return return 2 as int;;
    }
    int int owned readonly nonnull a <- unwrap(lend first_conversion as result) because as int;;

    result result owned mutable nonnull second_input <- input(lend "second: " as string) because as result;;
    bool bool owned readonly nonnull second_input_ok <- inspect(lend second_input as result) because as bool;;
    if second_input_failed ((!second_input_ok as bool)) {
        return return 3 as int;;
    }
    string string owned readonly nonnull second_text <- unwrap(lend second_input as result) because as string;;
    result result owned mutable nonnull second_conversion <- atoi(lend second_text as string) because as result;;
    bool bool owned readonly nonnull second_conversion_ok <- inspect(lend second_conversion as result) because as bool;;
    if second_conversion_failed ((!second_conversion_ok as bool)) {
        return return 4 as int;;
    }
    int int owned readonly nonnull b <- unwrap(lend second_conversion as result) because as int;;

    println(lend "sum:" as string, lend a + b as int) because;;
    return return 0 as int;;
}
