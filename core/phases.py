from skyfield import almanac


def new_moons(eph, start, end):

    phase_func = almanac.moon_phases(eph)

    times, phases = almanac.find_discrete(
        start,
        end,
        phase_func
    )

    # Lua Nova = fase 0
    return times[phases == 0]