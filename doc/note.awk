# extract version notes for version VER

/^[-_0-9a-zA-Z]+ v?[0-9]/ {
    if ($2 == VER) {
        good = 1
        next
    } else {
        good = 0
    }
}

/^(===|---)/ { next }

{
    if (good) {
        # also remove sphinx syntax
        print gensub(/:(\w+):`([^`]+)`/, "``\\2``", "g")
    }
}

