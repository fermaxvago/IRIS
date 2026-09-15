from iris.core.system import get_system_info, format_system_info


def main():
    print("IRIS v0.1 iniciando...")
    print("Hola Fernando. Soy IRIS.")
    print("Modo: local")
    print("Escribe 'estado', 'ayuda' o 'salir'.")

    while True:
        user_input = input("IRIS> ").strip().lower()

        if user_input == "salir":
            print("IRIS apagándose.")
            break

        if user_input == "ayuda":
            print("Comandos disponibles: estado, ayuda, salir")
            continue

        if user_input == "estado":
            info = get_system_info()
            print(format_system_info(info))
            continue

        print("Todavía no sé hacer eso, pero lo voy a aprender.")


if __name__ == "__main__":
    main()

