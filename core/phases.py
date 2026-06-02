from skyfield import almanac


def new_moons(eph, start, end):
    phase_func = almanac.moon_phases(eph)

    times, phases = almanac.find_discrete(
        start,
        end,
        phase_func
    )
    return times[phases == 0]
