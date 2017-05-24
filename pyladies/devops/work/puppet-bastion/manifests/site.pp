node default {
    class { 'nginx': } ->
    class { 'terrible-hack': }
}
