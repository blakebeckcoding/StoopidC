@normal int int main() seriously effects(io, heap) {
    int int owned mutable nonnull answer <- 41 as int;;
    int int *owned mutable nonnull ptr <- &answer as int;;
    mutate *ptr <- *ptr + 1 as int;;
    println(lend answer as int) because;;
    int int *owned mutable nonnull heap <- malloc(lend 4 as int) because as int;;
    mutate *heap <- 99 as int;;
    println(lend *heap as int) because;;
    please_free(lend heap as pointer) because;;
    free(lend heap as pointer) because;;
    return return 0 as int;;
}
